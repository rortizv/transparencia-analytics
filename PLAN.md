# TransparencIA — Plan de desarrollo

Auditor conversacional de contratación pública colombiana.
Concurso: **Datos al Ecosistema 2026 — MinTIC Colombia**.

---

## Stack

| Capa | Tecnología |
|---|---|
| Frontend | Next.js 16, App Router, TypeScript strict, Tailwind CSS, shadcn/ui |
| AI SDK | Vercel AI SDK v6 (`ai@6`, `@ai-sdk/azure`) |
| LLM | Azure OpenAI GPT-4o + text-embedding-3-small |
| Backend | Python 3.12, FastAPI, pydantic v2, psycopg3, sodapy |
| Base de datos | Neon Postgres + pgvector |
| Datos | SECOP II — dataset `jbjy-vk9h` en datos.gov.co (Socrata) |

**Convenciones:** código y nombres en inglés · conventional commits · TypeScript strict · type hints en todo el Python.

**Repos:**
- `transparencia-web` → frontend + chat handler
- `transparencia-analytics` → ingest pipeline + FastAPI endpoints

---

## Sprint 1 — Infraestructura base

### T-04.1 — Scaffold transparencia-web ✅
- [x] create-next-app con App Router, TypeScript, Tailwind, ESLint
- [x] shadcn/ui inicializado (estilo base-nova, Tailwind v4)
- [x] Vercel AI SDK v6 instalado (`ai`, `@ai-sdk/azure`)
- [x] `src/lib/azure-openai.ts` — cliente Azure OpenAI reutilizable (gpt4o + embeddingModel)
- [x] `.env.local.example` con todas las variables

### T-04.2 — Scaffold transparencia-analytics ✅
- [x] `pyproject.toml` con todas las dependencias (FastAPI, psycopg3, psycopg-pool, pgvector, pandas, scikit-learn, sodapy, openai, ruff, mypy, pytest)
- [x] Estructura de paquete: `src/transparencia/{main,config,db,api,ingest}`
- [x] `config.py` — pydantic-settings con todas las env vars
- [x] `db/connection.py` — AsyncConnectionPool (psycopg3)
- [x] `api/routers/health.py` — GET /health funcional
- [x] `api/routers/contracts.py` — stub GET /api/v1/contracts
- [x] `ingest/socrata.py` — factory del cliente Socrata
- [x] `tests/test_health.py` — test base con TestClient
- [x] `.venv` instalado y verificado (`from transparencia.main import app` OK)
- [x] `.env.example` con variables incluyendo Socrata

### T-04.3 — Route handler /api/chat en transparencia-web ✅
- [x] `src/app/api/chat/route.ts` creado con:
  - Tool `consultarSecop` (Socrata SECOP II, dataset jbjy-vk9h)
  - Campos: nombre_entidad, nit_entidad, nombre_del_proveedor_adjudicado, nit_del_proveedor, objeto_del_contrato, valor_del_contrato, modalidad_de_contratacion, departamento, fecha_de_firma, url_proceso
  - Filtros SoQL: departamento + año por detección de keywords
  - Limit 50, order by valor_del_contrato DESC
  - System prompt: agente TransparencIA, "patrón inusual"/"bandera roja", citar url_proceso
- [x] `src/app/page.tsx` — Chat UI con AI SDK v6 (`sendMessage`, `status`, `parts`)
- [x] Adaptado a AI SDK v6: `inputSchema+zodSchema`, `stopWhen:stepCountIs(5)`, `toUIMessageStreamResponse()`
- [x] `@ai-sdk/react` instalado; `isTextUIPart` para renderizar mensajes
- [x] `azure-openai.ts` refactorizado como factory functions (sin crash en import)
- [x] `tsc --noEmit` limpio, servidor levanta en 290ms
- [x] Endpoint responde 500 con mensaje claro "AZURE_OPENAI_ENDPOINT is not set" (falta .env.local)

---

## Sprint 1 — Pendiente

### T-04.4 — Migración SQL inicial en transparencia-analytics ✅
- [x] `db/migrations/001_initial_schema.sql`: pgvector, tabla `contracts` (25 cols), embedding vector(1536), flags JSONB, familia_unspsc GENERATED ALWAYS, 8 índices, trigger updated_at
- [x] Ejecutada contra Neon — 8 tests pasan en 2.62s

### T-04.5 — Pipeline de ingestión SECOP II ✅
- [x] `ingest/secop_pipeline.py`: fetch paginado Socrata, clean pandas, embeddings Azure OpenAI (batches 100), upsert psycopg3
- [x] CLI: `python -m transparencia.ingest.secop_pipeline [--since] [--limit] [--skip-embeddings]`

### T-04.6 — Endpoint /api/v1/contracts implementado ✅
- [x] `GET /api/v1/contracts` con filtros: departamento, year, entidad, proveedor, min/max_valor, estado
- [x] `GET /api/v1/contracts/{id}` — detalle de contrato (404 si no existe)
- [x] Búsqueda semántica (`?q=...`) con pgvector cosine similarity (`<=>`)
- [x] Paginación por offset (page + page_size)

---

## Sprint 2 — Agente conversacional

### T-05.1 — Mejorar system prompt y tools del agente ✅
- [x] System prompt refinado: prioridad buscarEnDB → consultarSecop fallback, sin duplicar lista
- [x] Tool `buscarEnDB` — llama a FastAPI /api/v1/contracts con búsqueda semántica pgvector
- [x] Tool `consultarSecop` — fallback en tiempo real a Socrata
- [x] `ANALYTICS_API_URL` env var para conectar frontend con backend

### T-05.2 — UI de chat mejorada ✅
- [x] Contract cards: valor (M/B COP), entidad, proveedor, departamento, fecha, estado, link
- [x] Indicador de herramienta animado ("🔍 Buscando..." / "🌐 Consultando SECOP II...")
- [x] Cards + texto unificados en un solo bubble del asistente
- [x] Empty state con 4 preguntas sugeridas clickeables
- [x] Favicon SVG (lupa azul)
- [ ] Historial persistente en localStorage ⏳

### T-05.3 — Detección de banderas rojas ✅
- [x] `ingest/flag_contracts.py`: 5 flags (contratacion_directa, proveedor_frecuente, valor_alto_sector, sin_proceso_url, plazo_muy_corto)
- [x] Badges rojos 🚩 en las contract cards
- [ ] Tool del agente para consultar contratos flaggeados ⏳

---

## Sprint 3 — Producción

### T-06.1 — Deploy transparencia-web a Vercel ✅
- [x] Proyecto `transparencia` creado en Vercel, linkeado a GitHub
- [x] Variables de entorno configuradas (Azure OpenAI, ANALYTICS_API_URL)
- [x] Live en https://transparencia-chi.vercel.app
- [x] Streaming funciona en producción

### T-06.2 — Deploy transparencia-analytics ⏳
- [ ] Contenedor Docker o Railway/Render para FastAPI
- [ ] Variables de entorno de producción
- [ ] Actualizar ANALYTICS_API_URL en Vercel con la URL real

### T-06.3 — CORS + autenticación básica ⏳
- [ ] CORS configurado en FastAPI para transparencia-chi.vercel.app
- [ ] API key simple entre frontend y backend (si se necesita)

---

## Ingestión de datos

- `ingest/secop_pipeline.py` — fetch + clean + embed + upsert (CLI)
- `ingest/embed_missing.py` — embede contratos sin embedding, commitea por lotes (resumible)
- `ingest/flag_contracts.py` — detecta banderas rojas y escribe en flags JSONB

**Estado actual:** fetch de 462k contratos 2024+ en curso sin embeddings.
**Siguiente:** `python -m transparencia.ingest.embed_missing` → `python -m transparencia.ingest.flag_contracts`

---

## Próximo paso inmediato

**T-06.2** — Deploy FastAPI a Railway o Render para activar búsqueda semántica en producción.
