"""
SECOP II ingestion pipeline.

Fetches contracts from Socrata (datos.gov.co), cleans them with pandas,
generates embeddings with Azure OpenAI, and upserts to Neon Postgres.

Usage:
    python -m transparencia.ingest.secop_pipeline
    python -m transparencia.ingest.secop_pipeline --limit 500 --since 2023-01-01
"""

import argparse
import logging
import sys
import time
from datetime import date, timedelta
from typing import Any

import pandas as pd
import psycopg
from openai import AzureOpenAI

from transparencia.config import settings
from transparencia.ingest.socrata import get_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

DATASET_ID = "jbjy-vk9h"
DEFAULT_PAGE_SIZE = 1_000
EMBEDDING_BATCH_SIZE = 100  # Azure OpenAI limit per request
MIN_VALUE_COP = 50_000_000  # 50M COP — filter noise

SOCRATA_FIELDS = [
    "id_contrato",
    "nombre_entidad",
    "nit_entidad",
    "departamento",
    "ciudad",
    "orden",
    "sector",
    "objeto_del_contrato",
    "tipo_de_contrato",
    "modalidad_de_contratacion",
    "valor_del_contrato",
    "fecha_de_firma",
    "fecha_de_inicio_del_contrato",
    "fecha_de_fin_del_contrato",
    "estado_contrato",
    "proveedor_adjudicado",
    "documento_proveedor",
    "es_pyme",
    "codigo_de_categoria_principal",
    "urlproceso",
]

DB_COLUMNS = [
    "id_contrato",
    "nombre_entidad",
    "nit_entidad",
    "departamento",
    "ciudad",
    "orden",
    "sector",
    "objeto_del_contrato",
    "tipo_de_contrato",
    "modalidad_de_contratacion",
    "valor_del_contrato",
    "fecha_de_firma",
    "fecha_de_inicio",
    "fecha_de_fin",
    "estado_contrato",
    "proveedor_adjudicado",
    "documento_proveedor",
    "es_pyme",
    "codigo_categoria_principal",
    "urlproceso",
]


# ── Fetch ────────────────────────────────────────────────────────────────────

FETCH_RETRIES = 5
FETCH_BACKOFF = 15  # seconds between retries


def fetch_page(client: Any, since: str, offset: int, page_size: int) -> list[dict]:
    where = (
        f"fecha_de_firma >= '{since}T00:00:00.000' "
        f"AND valor_del_contrato >= {MIN_VALUE_COP}"
    )
    last_exc: Exception | None = None
    for attempt in range(1, FETCH_RETRIES + 1):
        try:
            return client.get(
                DATASET_ID,
                select=",".join(SOCRATA_FIELDS),
                where=where,
                order="fecha_de_firma DESC",
                limit=page_size,
                offset=offset,
            )
        except Exception as exc:
            last_exc = exc
            wait = FETCH_BACKOFF * attempt
            log.warning(
                "Socrata error (attempt %d/%d) at offset=%d: %s — retrying in %ds",
                attempt, FETCH_RETRIES, offset, exc, wait,
            )
            time.sleep(wait)
    raise RuntimeError(f"Failed after {FETCH_RETRIES} retries at offset={offset}") from last_exc


# FETCH_BATCH_SIZE controls how many Socrata pages we accumulate before upserting.
# Keeps memory low and saves progress incrementally.
FETCH_BATCH_PAGES = 20  # 20 pages × 1 000 rows = 20 000 rows per upsert wave


def run_streaming(
    since: str,
    limit: int | None,
    page_size: int,
    skip_embeddings: bool,
) -> None:
    """Fetch → clean → (embed) → upsert in waves of FETCH_BATCH_PAGES pages.
    Progress is saved after each wave, so a crash only loses the current wave."""
    client = get_client()
    offset = 0
    total_fetched = 0
    total_upserted = 0

    while True:
        frames: list[pd.DataFrame] = []
        pages_in_wave = 0

        # Accumulate one wave of pages
        while pages_in_wave < FETCH_BATCH_PAGES:
            effective_page = (
                min(page_size, limit - total_fetched) if limit else page_size
            )
            log.info("Fetching offset=%d page=%d", offset, effective_page)
            rows = fetch_page(client, since, offset, effective_page)
            if not rows:
                break
            frames.append(pd.DataFrame(rows))
            n = len(rows)
            total_fetched += n
            offset += n
            pages_in_wave += 1
            log.info("Fetched %d records so far", total_fetched)
            if limit and total_fetched >= limit:
                break
            if n < effective_page:
                break  # last page

        if not frames:
            break

        df_wave = pd.concat(frames, ignore_index=True)
        df_wave = clean(df_wave)
        if df_wave.empty:
            if pages_in_wave < FETCH_BATCH_PAGES:
                break
            continue

        if skip_embeddings:
            embeddings: list[list[float] | None] = [None] * len(df_wave)
        else:
            log.info("Generating embeddings for %d records in this wave…", len(df_wave))
            embeddings = generate_embeddings(df_wave, settings.azure_openai_embedding_deployment)

        inserted = upsert(df_wave, embeddings, settings.database_url)
        total_upserted += inserted
        log.info("Wave done — upserted %d (total so far: %d)", inserted, total_upserted)

        if pages_in_wave < FETCH_BATCH_PAGES:
            break  # reached end of Socrata results
        if limit and total_fetched >= limit:
            break

    log.info("Streaming ingest complete — %d records upserted total.", total_upserted)


# ── Clean ────────────────────────────────────────────────────────────────────

def clean(df: pd.DataFrame) -> pd.DataFrame:
    # Rename columns to match DB schema
    df = df.rename(columns={
        "codigo_de_categoria_principal": "codigo_categoria_principal",
        "fecha_de_inicio_del_contrato": "fecha_de_inicio",
        "fecha_de_fin_del_contrato": "fecha_de_fin",
    })

    # Add missing columns with None
    for col in DB_COLUMNS:
        if col not in df.columns:
            df[col] = None

    df = df[DB_COLUMNS].copy()

    # Coerce numeric
    df["valor_del_contrato"] = pd.to_numeric(df["valor_del_contrato"], errors="coerce")

    # Drop rows without primary key or value
    df = df.dropna(subset=["id_contrato", "valor_del_contrato"])
    df = df[df["valor_del_contrato"] >= MIN_VALUE_COP]

    # Normalize timestamps
    for col in ["fecha_de_firma", "fecha_de_inicio", "fecha_de_fin"]:
        df[col] = pd.to_datetime(df[col], errors="coerce", utc=True)
        df[col] = df[col].where(df[col].notna(), None)

    # Strip whitespace from text fields
    text_cols = [c for c in DB_COLUMNS if df[c].dtype == object]
    for col in text_cols:
        df[col] = df[col].str.strip().replace("", None)

    log.info("After cleaning: %d records", len(df))
    return df


# ── Embed ────────────────────────────────────────────────────────────────────

def build_embedding_text(row: pd.Series) -> str:
    parts = [
        row.get("objeto_del_contrato") or "",
        row.get("nombre_entidad") or "",
        row.get("proveedor_adjudicado") or "",
        row.get("departamento") or "",
        row.get("modalidad_de_contratacion") or "",
    ]
    return " | ".join(p for p in parts if p)


def generate_embeddings(df: pd.DataFrame, deployment: str) -> list[list[float] | None]:
    client = AzureOpenAI(
        azure_endpoint=settings.azure_openai_endpoint,
        api_key=settings.azure_openai_api_key,
        api_version="2024-02-01",
    )

    texts = [build_embedding_text(row) for _, row in df.iterrows()]
    embeddings: list[list[float] | None] = []

    for i in range(0, len(texts), EMBEDDING_BATCH_SIZE):
        batch = texts[i : i + EMBEDDING_BATCH_SIZE]
        log.info("Embedding batch %d-%d / %d", i, i + len(batch), len(texts))
        response = client.embeddings.create(input=batch, model=deployment)
        embeddings.extend(e.embedding for e in response.data)

    return embeddings


# ── Upsert ───────────────────────────────────────────────────────────────────

UPSERT_SQL = """
INSERT INTO contracts (
    id_contrato, nombre_entidad, nit_entidad, departamento, ciudad,
    orden, sector, objeto_del_contrato, tipo_de_contrato,
    modalidad_de_contratacion, valor_del_contrato, fecha_de_firma,
    fecha_de_inicio, fecha_de_fin, estado_contrato,
    proveedor_adjudicado, documento_proveedor, es_pyme,
    codigo_categoria_principal, urlproceso, embedding
)
VALUES (
    %(id_contrato)s, %(nombre_entidad)s, %(nit_entidad)s, %(departamento)s,
    %(ciudad)s, %(orden)s, %(sector)s, %(objeto_del_contrato)s,
    %(tipo_de_contrato)s, %(modalidad_de_contratacion)s,
    %(valor_del_contrato)s, %(fecha_de_firma)s, %(fecha_de_inicio)s,
    %(fecha_de_fin)s, %(estado_contrato)s, %(proveedor_adjudicado)s,
    %(documento_proveedor)s, %(es_pyme)s, %(codigo_categoria_principal)s,
    %(urlproceso)s, %(embedding)s
)
ON CONFLICT (id_contrato) DO UPDATE SET
    nombre_entidad          = EXCLUDED.nombre_entidad,
    valor_del_contrato      = EXCLUDED.valor_del_contrato,
    estado_contrato         = EXCLUDED.estado_contrato,
    urlproceso              = EXCLUDED.urlproceso,
    embedding               = COALESCE(EXCLUDED.embedding, contracts.embedding),
    updated_at              = NOW();
"""


BATCH_SIZE = 500


def upsert(df: pd.DataFrame, embeddings: list[list[float] | None], db_url: str) -> int:
    records = df.to_dict(orient="records")
    inserted = 0

    with psycopg.connect(db_url, autocommit=False) as conn:
        with conn.cursor() as cur:
            batch: list[dict[str, Any]] = []
            for record, emb in zip(records, embeddings):
                clean_record: dict[str, Any] = {
                    k: (None if pd.isna(v) else v) for k, v in record.items()
                }
                clean_record["embedding"] = emb
                batch.append(clean_record)

                if len(batch) >= BATCH_SIZE:
                    cur.executemany(UPSERT_SQL, batch)
                    conn.commit()
                    inserted += len(batch)
                    log.info("Upserted %d / %d", inserted, len(records))
                    batch = []

            if batch:
                cur.executemany(UPSERT_SQL, batch)
                conn.commit()
                inserted += len(batch)

    return inserted


# ── CLI ──────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    three_years_ago = (date.today() - timedelta(days=3 * 365)).isoformat()
    parser = argparse.ArgumentParser(description="Ingest SECOP II contracts into Neon.")
    parser.add_argument("--since", default=three_years_ago, help="ISO date (default: 3 years ago)")
    parser.add_argument("--limit", type=int, default=None, help="Max records to fetch (default: all)")
    parser.add_argument("--page-size", type=int, default=DEFAULT_PAGE_SIZE)
    parser.add_argument("--skip-embeddings", action="store_true", help="Skip embedding generation (faster testing)")
    return parser.parse_args()


def run(since: str, limit: int | None, page_size: int, skip_embeddings: bool) -> None:
    log.info("Starting SECOP II ingestion since=%s limit=%s", since, limit or "all")
    run_streaming(
        since=since,
        limit=limit,
        page_size=page_size,
        skip_embeddings=skip_embeddings,
    )


if __name__ == "__main__":
    args = parse_args()
    try:
        run(
            since=args.since,
            limit=args.limit,
            page_size=args.page_size,
            skip_embeddings=args.skip_embeddings,
        )
    except KeyboardInterrupt:
        log.info("Interrupted.")
        sys.exit(0)
