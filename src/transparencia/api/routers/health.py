from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from transparencia.db.connection import get_conn

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    version: str


class ReadyResponse(BaseModel):
    status: str
    version: str
    database: dict[str, Any]
    pgvector: dict[str, Any]
    contracts: dict[str, Any]
    indexes: list[str]


@router.api_route("/health", methods=["GET", "HEAD"], response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", version="0.1.0")


@router.get("/ready", response_model=ReadyResponse)
async def ready() -> ReadyResponse:
    db_info: dict[str, Any] = {"connected": False}
    vec_info: dict[str, Any] = {"installed": False}
    contracts_info: dict[str, Any] = {}
    indexes: list[str] = []
    status = "ok"

    try:
        async with get_conn() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT version()")
                row = await cur.fetchone()
                db_info = {"connected": True, "version": (row[0] if row else "").split(",")[0]}

                await cur.execute(
                    "SELECT extversion FROM pg_extension WHERE extname = 'vector'"
                )
                row = await cur.fetchone()
                vec_info = {"installed": bool(row), "version": row[0] if row else None}

                await cur.execute(
                    """
                    SELECT
                        COUNT(*)::int AS total,
                        COUNT(embedding)::int AS with_embedding,
                        COUNT(*) FILTER (WHERE flags <> '{}'::jsonb)::int AS with_flags
                    FROM contracts
                    """
                )
                row = await cur.fetchone()
                if row:
                    total, with_emb, with_flags = row
                    contracts_info = {
                        "total": total,
                        "with_embedding": with_emb,
                        "embedding_coverage": round(with_emb / total, 4) if total else 0.0,
                        "with_flags": with_flags,
                    }

                await cur.execute(
                    "SELECT indexname FROM pg_indexes WHERE tablename = 'contracts' ORDER BY indexname"
                )
                indexes = [r[0] for r in await cur.fetchall()]
    except Exception as exc:
        status = "degraded"
        db_info.setdefault("error", str(exc))

    return ReadyResponse(
        status=status,
        version="0.1.0",
        database=db_info,
        pgvector=vec_info,
        contracts=contracts_info,
        indexes=indexes,
    )
