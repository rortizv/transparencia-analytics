# TransparencIA — Analytics Architecture

## Overview

This repository contains two components that share the same Python environment and database connection:

- **`ingest/`** — SECOP data ingestion pipeline (fetches from Socrata API, cleans, embeds, loads to Postgres)
- **`api/`** — FastAPI microservice exposing statistical analysis endpoints consumed by the Next.js agent
- **`db/migrations/`** — Versioned SQL migrations for Neon Postgres

## How the pieces connect
