"""Validates the contracts table schema against Neon."""
import os
import pytest
import psycopg
from dotenv import load_dotenv

load_dotenv()

DB_URL = os.environ.get("DATABASE_URL", "")

SAMPLE_CONTRACT = {
    "id_contrato": "TEST-001-TRANSPARENCIA",
    "nombre_entidad": "GOBERNACIÓN DE PRUEBA",
    "nit_entidad": "900000001",
    "departamento": "Chocó",
    "ciudad": "Quibdó",
    "orden": "Territorial",
    "sector": "educacion",
    "objeto_del_contrato": "Contrato de prueba para validación de schema TransparencIA",
    "tipo_de_contrato": "Prestación de servicios",
    "modalidad_de_contratacion": "Contratación directa",
    "valor_del_contrato": 125_000_000,
    "fecha_de_firma": "2025-01-15T00:00:00+00:00",
    "estado_contrato": "Activo",
    "proveedor_adjudicado": "Proveedor de Prueba SAS",
    "documento_proveedor": "900000002",
    "es_pyme": "Si",
    "codigo_categoria_principal": "V1.72101500",
    "urlproceso": "https://community.secop.gov.co/test",
}


@pytest.fixture(scope="module")
def conn():
    assert DB_URL, "DATABASE_URL is not set in .env"
    with psycopg.connect(DB_URL) as c:
        yield c


def test_contracts_table_exists(conn):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'contracts'
            )
        """)
        assert cur.fetchone()[0], "Table 'contracts' does not exist"


def test_pgvector_extension(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT extname FROM pg_extension WHERE extname = 'vector'")
        assert cur.fetchone(), "pgvector extension is not installed"


def test_embedding_column_dimension(conn):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT atttypmod
            FROM pg_attribute
            JOIN pg_class ON pg_class.oid = pg_attribute.attrelid
            WHERE pg_class.relname = 'contracts'
              AND pg_attribute.attname = 'embedding'
        """)
        row = cur.fetchone()
        assert row is not None, "embedding column not found"
        assert row[0] == 1536, f"Expected dimension 1536, got {row[0]}"


def test_familia_unspsc_generated(conn):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT is_generated
            FROM information_schema.columns
            WHERE table_name = 'contracts' AND column_name = 'familia_unspsc'
        """)
        row = cur.fetchone()
        assert row is not None, "familia_unspsc column not found"
        assert row[0] == "ALWAYS", "familia_unspsc should be a generated column"


def test_flags_default_empty_jsonb(conn):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT column_default
            FROM information_schema.columns
            WHERE table_name = 'contracts' AND column_name = 'flags'
        """)
        row = cur.fetchone()
        assert row and "{}" in row[0], "flags should default to empty JSONB"


def test_insert_and_query_contract(conn):
    with conn.cursor() as cur:
        # Clean up any leftover from previous run
        cur.execute("DELETE FROM contracts WHERE id_contrato = %s", (SAMPLE_CONTRACT["id_contrato"],))

        cur.execute("""
            INSERT INTO contracts (
                id_contrato, nombre_entidad, nit_entidad, departamento, ciudad,
                orden, sector, objeto_del_contrato, tipo_de_contrato,
                modalidad_de_contratacion, valor_del_contrato, fecha_de_firma,
                estado_contrato, proveedor_adjudicado, documento_proveedor,
                es_pyme, codigo_categoria_principal, urlproceso
            ) VALUES (
                %(id_contrato)s, %(nombre_entidad)s, %(nit_entidad)s,
                %(departamento)s, %(ciudad)s, %(orden)s, %(sector)s,
                %(objeto_del_contrato)s, %(tipo_de_contrato)s,
                %(modalidad_de_contratacion)s, %(valor_del_contrato)s,
                %(fecha_de_firma)s, %(estado_contrato)s,
                %(proveedor_adjudicado)s, %(documento_proveedor)s,
                %(es_pyme)s, %(codigo_categoria_principal)s, %(urlproceso)s
            )
        """, SAMPLE_CONTRACT)
        conn.commit()

        cur.execute("""
            SELECT id_contrato, valor_del_contrato, familia_unspsc, flags, ingested_at
            FROM contracts
            WHERE id_contrato = %s
        """, (SAMPLE_CONTRACT["id_contrato"],))
        row = cur.fetchone()

    assert row is not None, "Contract not found after insert"
    assert row[0] == SAMPLE_CONTRACT["id_contrato"]
    assert row[1] == 125_000_000
    assert row[2] == "V1.721", "familia_unspsc should be first 6 chars of UNSPSC code"
    assert row[3] == {}, "flags should be empty dict by default"
    assert row[4] is not None, "ingested_at should be set automatically"


def test_flags_update(conn):
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE contracts
            SET flags = flags || '{"proveedor_unico": true, "score": 0.87}'::jsonb
            WHERE id_contrato = %s
        """, (SAMPLE_CONTRACT["id_contrato"],))
        conn.commit()

        cur.execute("SELECT flags FROM contracts WHERE id_contrato = %s",
                    (SAMPLE_CONTRACT["id_contrato"],))
        flags = cur.fetchone()[0]

    assert flags.get("proveedor_unico") is True
    assert flags.get("score") == 0.87


def test_cleanup(conn):
    with conn.cursor() as cur:
        cur.execute("DELETE FROM contracts WHERE id_contrato = %s",
                    (SAMPLE_CONTRACT["id_contrato"],))
        conn.commit()
        cur.execute("SELECT COUNT(*) FROM contracts WHERE id_contrato = %s",
                    (SAMPLE_CONTRACT["id_contrato"],))
        assert cur.fetchone()[0] == 0
