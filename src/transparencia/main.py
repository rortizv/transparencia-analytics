from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from transparencia.api.routers import contracts, health
from transparencia.config import settings
from transparencia.db.connection import close_pool, init_pool


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await init_pool()
    yield
    await close_pool()


app = FastAPI(
    title="TransparencIA Analytics API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://transparencia-chi.vercel.app",
        "https://*.vercel.app",
        "http://localhost:3000",
    ],
    allow_methods=["GET"],
    allow_headers=["*"],
)

@app.middleware("http")
async def require_api_key(request: Request, call_next: object) -> Response:
    if request.url.path == "/health":
        return await call_next(request)  # type: ignore[operator]
    if settings.api_key:
        key = request.headers.get("X-API-Key", "")
        if key != settings.api_key:
            return Response(content="Unauthorized", status_code=401)
    return await call_next(request)  # type: ignore[operator]


app.include_router(health.router)
app.include_router(contracts.router, prefix="/api/v1")
