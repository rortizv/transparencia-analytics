-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- SECOP II contracts table
CREATE TABLE IF NOT EXISTS contracts (
    -- Primary key from SECOP II
    id_contrato             TEXT PRIMARY KEY,

    -- Entity
    nombre_entidad          TEXT,
    nit_entidad             TEXT,
    departamento            TEXT,
    ciudad                  TEXT,
    orden                   TEXT,
    sector                  TEXT,

    -- Contract details
    objeto_del_contrato     TEXT,
    tipo_de_contrato        TEXT,
    modalidad_de_contratacion TEXT,
    valor_del_contrato      NUMERIC,
    fecha_de_firma          TIMESTAMPTZ,
    fecha_de_inicio         TIMESTAMPTZ,
    fecha_de_fin            TIMESTAMPTZ,
    estado_contrato         TEXT,

    -- Provider
    proveedor_adjudicado    TEXT,
    documento_proveedor     TEXT,
    es_pyme                 TEXT,

    -- Classification
    codigo_categoria_principal TEXT,

    -- Generated column: first 4 digits of UNSPSC code (family level)
    familia_unspsc          TEXT GENERATED ALWAYS AS (
                                LEFT(codigo_categoria_principal, 6)
                            ) STORED,

    -- Anomaly flags (flexible JSONB for evolving detection rules)
    flags                   JSONB NOT NULL DEFAULT '{}',

    -- Source link
    urlproceso              TEXT,

    -- Embedding for semantic search (text-embedding-3-small = 1536 dims)
    embedding               vector(1536),

    -- Ingestion metadata
    ingested_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_contracts_departamento
    ON contracts (departamento);

CREATE INDEX IF NOT EXISTS idx_contracts_fecha_de_firma
    ON contracts (fecha_de_firma DESC);

CREATE INDEX IF NOT EXISTS idx_contracts_valor
    ON contracts (valor_del_contrato DESC);

CREATE INDEX IF NOT EXISTS idx_contracts_nit_entidad
    ON contracts (nit_entidad);

CREATE INDEX IF NOT EXISTS idx_contracts_documento_proveedor
    ON contracts (documento_proveedor);

CREATE INDEX IF NOT EXISTS idx_contracts_familia_unspsc
    ON contracts (familia_unspsc);

CREATE INDEX IF NOT EXISTS idx_contracts_flags
    ON contracts USING GIN (flags);

-- HNSW vector index — create AFTER initial bulk load, not before
-- Run this manually once the first batch is loaded:
--
--   CREATE INDEX idx_contracts_embedding
--       ON contracts USING hnsw (embedding vector_cosine_ops)
--       WITH (m = 16, ef_construction = 64);

-- Auto-update updated_at on row changes
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

CREATE OR REPLACE TRIGGER contracts_updated_at
    BEFORE UPDATE ON contracts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
