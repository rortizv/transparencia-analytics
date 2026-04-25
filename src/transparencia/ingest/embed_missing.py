"""
Generate and store embeddings for contracts that don't have one yet.

Reads directly from the DB (WHERE embedding IS NULL), embeds in batches,
and commits each batch immediately — safe to kill and resume at any time.

Usage:
    python -m transparencia.ingest.embed_missing
    python -m transparencia.ingest.embed_missing --batch-size 200
"""

import argparse
import logging
import sys
import time

import psycopg
from openai import AzureOpenAI

from transparencia.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

EMBEDDING_BATCH = 100  # Azure OpenAI max per request


def build_text(row: dict[str, str | None]) -> str:
    parts = [
        row.get("objeto_del_contrato") or "",
        row.get("nombre_entidad") or "",
        row.get("proveedor_adjudicado") or "",
        row.get("departamento") or "",
        row.get("modalidad_de_contratacion") or "",
    ]
    return " | ".join(p for p in parts if p)


def embed_batch(client: AzureOpenAI, texts: list[str], deployment: str) -> list[list[float]]:
    while True:
        try:
            response = client.embeddings.create(input=texts, model=deployment)
            return [e.embedding for e in response.data]
        except Exception as e:
            msg = str(e)
            if "429" in msg or "rate" in msg.lower():
                wait = 60
                log.warning("Rate limited — waiting %ds", wait)
                time.sleep(wait)
            else:
                raise


def run(batch_size: int) -> None:
    client = AzureOpenAI(
        azure_endpoint=settings.azure_openai_endpoint,
        api_key=settings.azure_openai_api_key,
        api_version="2024-02-01",
    )
    deployment = settings.azure_openai_embedding_deployment

    with psycopg.connect(settings.database_url) as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM contracts WHERE embedding IS NULL")
        row0 = cur.fetchone()
        total_missing: int = row0[0] if row0 else 0
        log.info("Contracts without embedding: %d", total_missing)

        processed = 0
        while True:
            cur.execute(
                """
                SELECT id_contrato, objeto_del_contrato, nombre_entidad,
                       proveedor_adjudicado, departamento, modalidad_de_contratacion
                FROM   contracts
                WHERE  embedding IS NULL
                LIMIT  %s
                """,
                (batch_size,),
            )
            rows = cur.fetchall()
            cols = [d.name for d in (cur.description or [])]
            if not rows:
                break

            records = [dict(zip(cols, r)) for r in rows]
            texts = [build_text(r) for r in records]
            ids = [r["id_contrato"] for r in records]

            # Embed in sub-batches of EMBEDDING_BATCH
            embeddings: list[list[float]] = []
            for i in range(0, len(texts), EMBEDDING_BATCH):
                sub = texts[i : i + EMBEDDING_BATCH]
                log.info(
                    "Embedding %d-%d / ~%d remaining",
                    processed + i,
                    processed + i + len(sub),
                    total_missing - processed,
                )
                embeddings.extend(embed_batch(client, sub, deployment))

            # Commit this batch immediately
            for id_contrato, emb in zip(ids, embeddings):
                vec = "[" + ",".join(str(x) for x in emb) + "]"
                cur.execute(
                    "UPDATE contracts SET embedding = %s::vector WHERE id_contrato = %s",
                    (vec, id_contrato),
                )
            conn.commit()
            processed += len(records)
            log.info("Committed %d / %d", processed, total_missing)

    log.info("Done. %d contracts embedded.", processed)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Embed contracts missing embeddings.")
    p.add_argument("--batch-size", type=int, default=500,
                   help="Records per DB fetch + commit cycle (default: 500)")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    try:
        run(args.batch_size)
    except KeyboardInterrupt:
        log.info("Interrupted — safe to resume, progress is committed.")
        sys.exit(0)
