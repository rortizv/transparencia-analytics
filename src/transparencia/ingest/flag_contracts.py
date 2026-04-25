"""
Red flag detection for SECOP II contracts.

Detects anomaly patterns and writes them to the `flags` JSONB column:
  - contratacion_directa: awarded without competitive process
  - proveedor_frecuente:  provider won 5+ contracts with same entity
  - valor_alto_sector:    value > 3× median for same sector/department
  - sin_proceso_url:      no urlproceso (opacity risk)
  - plazo_muy_corto:      contract duration < 7 days

Usage:
    python -m transparencia.ingest.flag_contracts
"""

import argparse
import logging
import sys

import psycopg

from transparencia.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ── Flag queries ───────────────────────────────────────────────────────────────
# Each query must produce (id_contrato, flag_value) rows.
# flag_value must be JSON-serialisable; use SQL casting where needed.

FLAG_QUERIES: list[tuple[str, str]] = [

    ("contratacion_directa", """
        SELECT id_contrato,
               modalidad_de_contratacion AS flag_value
        FROM   contracts
        WHERE  modalidad_de_contratacion ILIKE '%directa%'
    """),

    ("sin_proceso_url", """
        SELECT id_contrato,
               true::text AS flag_value
        FROM   contracts
        WHERE  urlproceso IS NULL OR urlproceso = ''
    """),

    ("plazo_muy_corto", """
        SELECT id_contrato,
               EXTRACT(DAY FROM fecha_de_fin - fecha_de_inicio)::int::text AS flag_value
        FROM   contracts
        WHERE  fecha_de_inicio IS NOT NULL
          AND  fecha_de_fin    IS NOT NULL
          AND  fecha_de_fin > fecha_de_inicio
          AND  EXTRACT(DAY FROM fecha_de_fin - fecha_de_inicio) < 7
    """),

    ("proveedor_frecuente", """
        WITH freq AS (
            SELECT documento_proveedor, nit_entidad, COUNT(*) AS n
            FROM   contracts
            WHERE  documento_proveedor IS NOT NULL
              AND  nit_entidad         IS NOT NULL
            GROUP  BY documento_proveedor, nit_entidad
            HAVING COUNT(*) >= 5
        )
        SELECT c.id_contrato,
               f.n::text AS flag_value
        FROM   contracts c
        JOIN   freq f USING (documento_proveedor, nit_entidad)
    """),

    ("valor_alto_sector", """
        WITH stats AS (
            SELECT sector,
                   departamento,
                   PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY valor_del_contrato) AS mediana
            FROM   contracts
            WHERE  sector            IS NOT NULL
              AND  departamento      IS NOT NULL
              AND  valor_del_contrato > 0
            GROUP  BY sector, departamento
        )
        SELECT c.id_contrato,
               ROUND((c.valor_del_contrato / s.mediana)::numeric, 1)::float::text AS flag_value
        FROM   contracts c
        JOIN   stats s USING (sector, departamento)
        WHERE  s.mediana > 0
          AND  c.valor_del_contrato > s.mediana * 3
    """),
]


# ── Core ──────────────────────────────────────────────────────────────────────

def run_flags(db_url: str, batch_size: int) -> None:
    with psycopg.connect(db_url, autocommit=False) as conn:
        log.info("Resetting existing flags...")
        conn.execute("UPDATE contracts SET flags = '{}'::jsonb")
        conn.commit()
        log.info("Flags reset.")

        for flag_key, query in FLAG_QUERIES:
            log.info("Computing flag: %s", flag_key)
            rows = conn.execute(query).fetchall()
            total = len(rows)
            log.info("  → %d contracts to flag", total)

            # Bulk UPDATE using unnest — orders of magnitude faster than row-by-row
            for i in range(0, total, batch_size):
                batch = rows[i : i + batch_size]
                ids = [r[0] for r in batch]
                vals = [r[1] for r in batch]
                conn.execute(
                    f"""
                    UPDATE contracts AS c
                    SET    flags = flags || jsonb_build_object('{flag_key}', to_jsonb(v.fv))
                    FROM   unnest(%s::text[], %s::text[]) AS v(id, fv)
                    WHERE  c.id_contrato = v.id
                    """,
                    (ids, vals),
                )
                conn.commit()
                log.info("  → committed %d / %d", min(i + batch_size, total), total)

            log.info("  ✓ %s: %d contracts flagged", flag_key, total)

    log.info("Done. All flags written.")


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Detect red flags in SECOP II contracts.")
    p.add_argument("--batch-size", type=int, default=10_000)
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    try:
        run_flags(settings.database_url, args.batch_size)
    except KeyboardInterrupt:
        log.info("Interrupted.")
        sys.exit(0)
