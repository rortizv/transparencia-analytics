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

### T-05.1 — Mejorar system prompt y tools del agente ⏳
- [ ] Refinar system prompt con más restricciones y ejemplos
- [ ] Tool `buscarPorSimilitud` — búsqueda vectorial en Neon
- [ ] Tool `analizarPatrones` — detectar anomalías (proveedor único, precio atípico)
- [ ] Conectar herramientas del frontend con API del backend (reemplazar fetch directo a Socrata)

### T-05.2 — UI de chat mejorada ⏳
- [ ] Renderizado de fuentes/contratos como cards (no solo texto plano)
- [ ] Indicador de herramienta en uso ("Consultando SECOP II…")
- [ ] Historial de conversación persistente (localStorage o DB)
- [ ] Metadata: título app, favicon

### T-05.3 — Detección de banderas rojas ⏳
- [ ] Lógica de flags en el backend: proveedor único, valor atípico, plazo inusual
- [ ] Almacenar flags en columna JSONB de la tabla contracts
- [ ] Tool del agente que consulta contratos flaggeados

---

## Sprint 3 — Producción

### T-06.1 — Deploy transparencia-web a Vercel ⏳
- [ ] Configurar variables de entorno en Vercel
- [ ] Verificar streaming funciona en edge runtime

### T-06.2 — Deploy transparencia-analytics ⏳
- [ ] Contenedor Docker o Railway/Render para FastAPI
- [ ] Variables de entorno de producción
- [ ] Health check en CI

### T-06.3 — CORS + autenticación básica ⏳
- [ ] CORS configurado en FastAPI para el dominio de Vercel
- [ ] API key simple entre frontend y backend (si se necesita)

---

## Contexto del equipo
- **Rafael (Tech Lead)** — arquitectura, frontend, integración AI
- **Alessandro** — API FastAPI (transparencia-analytics)
- **Giselle** — pipeline de ingestión SECOP II

---

## Próximo paso inmediato

**Retomar T-04.3** — corregir los 5 errores TypeScript en `transparencia-web`:
1. `npm install @ai-sdk/react`
2. Cambiar import `ai/react` → `@ai-sdk/react` en `page.tsx`
3. Cambiar `maxSteps: 5` → `stopWhen: stepCountIs(5)` en `route.ts`
4. Cambiar `toDataStreamResponse()` → `toTextStreamResponse()` en `route.ts`
5. Agregar tipo explícito al parámetro `query` en el `execute` del tool
6. Tipar el parámetro `m` en el map de messages en `page.tsx`
7. Levantar `npm run dev` y probar con pregunta de Chocó 2025
