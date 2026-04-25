-- HNSW index para búsqueda semántica sobre embeddings.
-- Ejecutar una sola vez después de tener todos los embeddings poblados.
-- m=16, ef_construction=64 es el balance estándar (calidad vs build time)
-- para datasets <1M vectores.

SET maintenance_work_mem = '512MB';

CREATE INDEX IF NOT EXISTS idx_contracts_embedding
    ON contracts USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- Verificación
SELECT
    indexname,
    pg_size_pretty(pg_relation_size(indexname::regclass)) AS size
FROM pg_indexes
WHERE tablename = 'contracts' AND indexname = 'idx_contracts_embedding';
