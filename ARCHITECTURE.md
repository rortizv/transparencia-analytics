# TransparencIA — Analytics Architecture

## Overview

This repository contains two components that share the same Python environment and database connection:

- **`ingest/`** — SECOP data ingestion pipeline (fetches from Socrata API, cleans, embeds, loads to Postgres)
- **`api/`** — FastAPI microservice exposing statistical analysis endpoints consumed by the Next.js agent
- **`db/migrations/`** — Versioned SQL migrations for Neon Postgres

## How the pieces connect

datos.gov.co (Socrata SODA API)
│
▼
ingest/ ← Giselle owns this
(Python + sodapy + pandas)
│
▼
Neon Postgres + pgvector
(table: contratos)
│
▼
api/ ← Alessandro owns this
(FastAPI + pandas + scikit-learn)
│
▼
transparencia-web
(Next.js agent calls /api endpoints as tools)

## Environment variables

Copy `.env.example` to `.env` and fill in your values. Never commit `.env`.

| Variable                            | Description                                              |
| ----------------------------------- | -------------------------------------------------------- |
| `DATABASE_URL`                      | Neon Postgres connection string (use dev branch locally) |
| `AZURE_OPENAI_ENDPOINT`             | Azure OpenAI resource endpoint                           |
| `AZURE_OPENAI_API_KEY`              | Azure OpenAI API key                                     |
| `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` | Deployment name for text-embedding-3-small               |

## Conventions

- **Language:** all code, variables, functions, classes and file names in English
- **Branch strategy:** work on dev, merge to main via PR
- **Commits:** conventional commits (feat:, fix:, chore:, docs:)
- **Python:** 3.12+, type hints required, pydantic v2 for data validation

## Database

- **Host:** Neon Postgres (serverless)
- **Branch dev:** for local development and CI
- **Branch production:** for the live application
- **pgvector:** enabled on both branches, used for semantic similarity search on contratos.embedding

## Running locally

```bash
# 1. Create virtual environment and install dependencies
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# 2. Copy env file
cp .env.example .env
# Fill in your Neon dev branch connection string and Azure keys

# 3. Run the API
uvicorn src.transparencia.main:app --reload

# 4. Run an ingest job
python -m src.transparencia.ingest.socrata --limit 1000
```

## Key decisions

- **No Databricks/Spark:** we filter at the source using SoQL. We only pull ~2-3M contracts (last 3 years, value > $50M COP), not the full 9M+ dataset
- **HNSW index:** created AFTER the initial bulk load, not before. Building it on an empty table wastes time
- **familia_unspsc:** generated column (first 4 digits of codigo_unspsc). Do not calculate it manually in the pipeline
- **flags as JSONB:** allows flexible anomaly tagging without extra tables
- **Single repo for ingest + api:** both share the same Python environment and DB connection. Split only if they grow significantly
