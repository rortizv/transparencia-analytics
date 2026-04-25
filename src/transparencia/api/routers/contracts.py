from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from openai import AzureOpenAI
from pydantic import BaseModel

from transparencia.config import settings
from transparencia.db.connection import get_conn

router = APIRouter(prefix="/contracts", tags=["contracts"])


# ── Response models ────────────────────────────────────────────────────────────

class Contract(BaseModel):
    id_contrato: str
    nombre_entidad: str | None
    nit_entidad: str | None
    departamento: str | None
    ciudad: str | None
    orden: str | None
    sector: str | None
    objeto_del_contrato: str | None
    tipo_de_contrato: str | None
    modalidad_de_contratacion: str | None
    valor_del_contrato: float | None
    fecha_de_firma: str | None
    fecha_de_inicio: str | None
    fecha_de_fin: str | None
    estado_contrato: str | None
    proveedor_adjudicado: str | None
    documento_proveedor: str | None
    es_pyme: str | None
    codigo_categoria_principal: str | None
    familia_unspsc: str | None
    urlproceso: str | None
    flags: dict[str, Any]


class ContractList(BaseModel):
    data: list[Contract]
    total: int
    page: int
    page_size: int


# ── Query helpers ──────────────────────────────────────────────────────────────

def _embed_query(text: str) -> list[float] | None:
    try:
        client = AzureOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            api_version="2024-02-01",
        )
        response = client.embeddings.create(
            input=text,
            model=settings.azure_openai_embedding_deployment,
        )
        return response.data[0].embedding
    except Exception:
        return None


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("", response_model=ContractList)
async def list_contracts(
    departamento: str | None = Query(None),
    year: int | None = Query(None, ge=2010, le=2030),
    entidad: str | None = Query(None),
    proveedor: str | None = Query(None),
    min_valor: float | None = Query(None),
    max_valor: float | None = Query(None),
    estado: str | None = Query(None),
    flag: str | None = Query(None, description="Filtrar por bandera roja: contratacion_directa | proveedor_frecuente | valor_alto_sector | sin_proceso_url | plazo_muy_corto"),
    q: str | None = Query(None, description="Semantic search query"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> ContractList:
    conditions: list[str] = []
    params: list[Any] = []

    if departamento:
        conditions.append(f"departamento ILIKE %s")
        params.append(f"%{departamento}%")

    if year:
        conditions.append("EXTRACT(YEAR FROM fecha_de_firma) = %s")
        params.append(year)

    if entidad:
        conditions.append("nombre_entidad ILIKE %s")
        params.append(f"%{entidad}%")

    if proveedor:
        conditions.append("proveedor_adjudicado ILIKE %s")
        params.append(f"%{proveedor}%")

    if min_valor is not None:
        conditions.append("valor_del_contrato >= %s")
        params.append(min_valor)

    if max_valor is not None:
        conditions.append("valor_del_contrato <= %s")
        params.append(max_valor)

    if estado:
        conditions.append("estado_contrato ILIKE %s")
        params.append(f"%{estado}%")

    if flag:
        conditions.append("flags ? %s")
        params.append(flag)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    offset = (page - 1) * page_size

    # Semantic search: re-rank by vector similarity when q is provided
    select_extra = ""
    if q and q.strip():
        embedding = _embed_query(q)
        if embedding is not None:
            vec_literal = "[" + ",".join(str(x) for x in embedding) + "]"
            order_clause = f"embedding <=> '{vec_literal}'::vector"
            select_extra = f", (embedding <=> '{vec_literal}'::vector) AS _dist"
        else:
            order_clause = "valor_del_contrato DESC NULLS LAST"
    else:
        order_clause = "valor_del_contrato DESC NULLS LAST"

    sql_count = f"SELECT COUNT(*) FROM contracts {where}"
    sql_data = f"""
        SELECT
            id_contrato, nombre_entidad, nit_entidad, departamento, ciudad,
            orden, sector, objeto_del_contrato, tipo_de_contrato,
            modalidad_de_contratacion, valor_del_contrato,
            fecha_de_firma::text, fecha_de_inicio::text, fecha_de_fin::text,
            estado_contrato, proveedor_adjudicado, documento_proveedor,
            es_pyme, codigo_categoria_principal, familia_unspsc, urlproceso,
            flags {select_extra}
        FROM contracts
        {where}
        ORDER BY {order_clause}
        LIMIT %s OFFSET %s
    """

    async with get_conn() as conn:
        async with conn.cursor() as cur:
            await cur.execute(sql_count, params)
            row = await cur.fetchone()
            total = row[0] if row else 0

            await cur.execute(sql_data, params + [page_size, offset])
            rows = await cur.fetchall()
            cols = [d.name for d in cur.description or []]

    contracts = []
    for row in rows:
        record = dict(zip(cols, row))
        record.pop("_dist", None)
        contracts.append(Contract(**record))

    return ContractList(data=contracts, total=total, page=page, page_size=page_size)


@router.get("/{id_contrato}", response_model=Contract)
async def get_contract(id_contrato: str) -> Contract:
    sql = """
        SELECT
            id_contrato, nombre_entidad, nit_entidad, departamento, ciudad,
            orden, sector, objeto_del_contrato, tipo_de_contrato,
            modalidad_de_contratacion, valor_del_contrato,
            fecha_de_firma::text, fecha_de_inicio::text, fecha_de_fin::text,
            estado_contrato, proveedor_adjudicado, documento_proveedor,
            es_pyme, codigo_categoria_principal, familia_unspsc, urlproceso,
            flags
        FROM contracts
        WHERE id_contrato = %s
    """
    async with get_conn() as conn:
        async with conn.cursor() as cur:
            await cur.execute(sql, [id_contrato])
            row = await cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Contract not found")
            cols = [d.name for d in cur.description or []]
            return Contract(**dict(zip(cols, row)))
