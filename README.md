# TransparencIA

**Auditor conversacional de contratacion publica colombiana**

TransparencIA permite que cualquier ciudadano audite contratos del SECOP II haciendo preguntas en lenguaje natural. Sin formularios, sin filtros tecnicos, sin conocimientos juridicos previos: solo escribe tu pregunta y el sistema busca, analiza y detecta posibles irregularidades en mas de 100 000 contratos publicos.

Proyecto presentado al concurso **MinTIC "Datos al Ecosistema 2026"**.

---

## Por que importa

Colombia publica sus contratos estatales en el Sistema Electronico de Contratacion Publica (SECOP II), pero la plataforma oficial exige conocer codigos UNSPSC, rangos de fechas exactos y filtros avanzados que la mayoria de ciudadanos no sabe usar. El resultado es que los datos existen pero son inaccesibles en la practica.

TransparencIA convierte esa base de datos en una conversacion. Un periodista puede preguntar "contratos directos mayores a 500 millones en Choco en 2024". Un veedor puede preguntar "proveedores que aparecen mas de 10 veces en contratos de Bogota este ano". El sistema responde en segundos con los contratos relevantes y las alertas de riesgo correspondientes.

---

## Demo en vivo

| Componente     | URL                                                |
| -------------- | -------------------------------------------------- |
| Aplicacion web | https://transparencia-chi.vercel.app               |
| API backend    | https://web-production-2a830.up.railway.app/health |

---

## Funcionalidades principales

- **Busqueda en lenguaje natural** — preguntas en espanol coloquial, sin sintaxis especial
- **Busqueda semantica con pgvector** — encuentra contratos por significado, no solo por palabras clave exactas
- **5 detectores de alertas de riesgo:**
  - `contratacion_directa` — contratos adjudicados sin licitacion publica
  - `proveedor_frecuente` — mismo proveedor aparece repetidamente con la misma entidad
  - `valor_alto_sector` — valor del contrato supera 2 desviaciones estandar de su sector
  - `sin_proceso_url` — contrato sin enlace verificable al proceso en SECOP II
  - `plazo_muy_corto` — plazo de ejecucion menor a 7 dias habiles
- **Tarjetas de contrato** con valor, entidad, proveedor, departamento, fecha y badges de alerta
- **Historial de chat** persistido en localStorage
- **Modo oscuro / claro**

---

## Arquitectura

```
  Usuario (navegador)
       |
       | HTTPS
       v
+------------------+
|   Next.js 16     |  Vercel (Edge)
|   TypeScript     |
|   Tailwind CSS   |
|   Vercel AI SDK  |
+--------+---------+
         |
         | /api/chat  (streaming)
         v
+------------------+
|  Azure OpenAI    |  GPT-4o  (LLM)
|  GPT-4o          |  text-embedding-3-small  (embeddings)
+--------+---------+
         |
         | REST + JSON
         v
+------------------+
|   FastAPI        |  Railway
|   Python 3.12    |
|   psycopg3       |
+--------+---------+
         |
         | pgvector  (ANN search)
         v
+------------------+
|  Neon Postgres   |  100 000+ contratos SECOP II
|  pgvector ext.   |  embeddings dim=1536
+------------------+
         ^
         | ingesta diaria
+------------------+
|  datos.gov.co    |  Socrata API  (SECOP II dataset)
+------------------+
```

---

## Repositorios

| Repo                      | Descripcion                                                  |
| ------------------------- | ------------------------------------------------------------ |
| `transparencia-web`       | Frontend Next.js + manejador de chat con Vercel AI SDK       |
| `transparencia-analytics` | Backend FastAPI + pipeline de ingesta y deteccion de alertas |

---

## Ejecutar localmente

### Requisitos previos

- Node.js >= 20
- Python 3.12
- Una base de datos Postgres con la extension `pgvector` instalada (o cuenta Neon gratuita)
- Credenciales de Azure OpenAI con despliegues de `gpt-4o` y `text-embedding-3-small`

### 1. Backend (transparencia-analytics)

```bash
cd transparencia-analytics
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # completar variables (ver seccion siguiente)
uvicorn transparencia.main:app --app-dir src --reload --port 8000
```

La API quedara disponible en `http://localhost:8000`. Verificar con:

```bash
curl http://localhost:8000/health
```

### 2. Frontend (transparencia-web)

```bash
cd transparencia-web
npm install
cp .env.local.example .env.local   # completar variables
npm run dev
```

La aplicacion quedara disponible en `http://localhost:3000`.

---

## Variables de entorno

### Backend (`transparencia-analytics/.env`)

| Variable                     | Descripcion                                                                       |
| ---------------------------- | --------------------------------------------------------------------------------- |
| `DATABASE_URL`               | Cadena de conexion Postgres con pgvector, p. ej. `postgresql://user:pass@host/db` |
| `AZURE_OPENAI_ENDPOINT`      | Endpoint de Azure OpenAI, p. ej. `https://mi-recurso.openai.azure.com/`           |
| `AZURE_OPENAI_API_KEY`       | Clave de API de Azure OpenAI                                                      |
| `AZURE_OPENAI_DEPLOYMENT`    | Nombre del despliegue GPT-4o, p. ej. `gpt-4o`                                     |
| `AZURE_EMBEDDING_DEPLOYMENT` | Nombre del despliegue de embeddings, p. ej. `text-embedding-3-small`              |
| `SOCRATA_APP_TOKEN`          | Token de la API de datos.gov.co (opcional, aumenta el limite de peticiones)       |

### Frontend (`transparencia-web/.env.local`)

| Variable                  | Descripcion                                             |
| ------------------------- | ------------------------------------------------------- |
| `ANALYTICS_API_URL`       | URL del backend FastAPI, p. ej. `http://localhost:8000` |
| `AZURE_OPENAI_ENDPOINT`   | Endpoint de Azure OpenAI                                |
| `AZURE_OPENAI_API_KEY`    | Clave de API de Azure OpenAI                            |
| `AZURE_OPENAI_DEPLOYMENT` | Nombre del despliegue GPT-4o                            |

---

## Datos y metodologia

### Fuente de datos

Los contratos provienen del dataset oficial **SECOP II** publicado en [datos.gov.co](https://www.datos.gov.co) a traves de la API Socrata. El pipeline de ingesta descarga incrementalmente los contratos nuevos y actualizados, normaliza los campos criticos (valor, fechas, departamento, modalidad de contratacion) y genera un embedding vectorial por contrato usando `text-embedding-3-small`.

### Busqueda semantica

Cada contrato se representa como un vector de 1536 dimensiones calculado sobre un texto que concatena objeto del contrato, entidad, proveedor y modalidad. Las consultas del usuario se convierten al mismo espacio vectorial y se ejecuta una busqueda de vecinos mas cercanos con el operador `<=>` de pgvector (distancia coseno). Esto permite encontrar contratos relevantes aunque el usuario use sinonimos o descripciones distintas a las que aparecen en el documento original.

### Deteccion de alertas

Las alertas no son acusaciones: son indicadores estadisticos que senalan contratos que se desvian del patron esperado para su sector, departamento o entidad. El modelo de lenguaje interpreta la pregunta del usuario, recupera los contratos mas relevantes y aplica los detectores de alerta sobre ese conjunto de resultados antes de generar la respuesta final.

| Alerta                 | Criterio                                                                                  |
| ---------------------- | ----------------------------------------------------------------------------------------- |
| `contratacion_directa` | Campo `modalidad_proceso` igual a "Contratacion Directa"                                  |
| `proveedor_frecuente`  | El mismo NIT de proveedor aparece >= 5 veces con la misma entidad en los ultimos 12 meses |
| `valor_alto_sector`    | Valor del contrato > media del sector + 2 \* desviacion estandar                          |
| `sin_proceso_url`      | Campo `url_proceso` nulo o vacio                                                          |
| `plazo_muy_corto`      | Diferencia entre fecha de inicio y fecha de fin < 7 dias calendario                       |

### Limitaciones conocidas

- El dataset de datos.gov.co puede tener retrasos de hasta 48 horas respecto a SECOP II.
- Los contratos de vigencias anteriores a 2020 tienen cobertura parcial.
- Las alertas son heuristicas exploratorias, no conclusiones juridicas.

---

## Stack tecnologico

| Capa                | Tecnologia                                             |
| ------------------- | ------------------------------------------------------ |
| Frontend            | Next.js 16, TypeScript, Tailwind CSS, Vercel AI SDK v6 |
| LLM                 | Azure OpenAI GPT-4o                                    |
| Embeddings          | Azure OpenAI text-embedding-3-small                    |
| Backend             | Python 3.12, FastAPI, psycopg3                         |
| Base de datos       | Neon Postgres + pgvector                               |
| Datos               | SECOP II via datos.gov.co (API Socrata)                |
| Despliegue frontend | Vercel                                                 |
| Despliegue backend  | Railway                                                |

---

## Licencia

MIT — uso libre para propositos civicos, periodisticos y academicos.
