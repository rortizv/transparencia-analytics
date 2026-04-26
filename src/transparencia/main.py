from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from transparencia.api.routers import contracts, conversations, health
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
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
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


@app.middleware("http")
async def security_headers(request: Request, call_next: object) -> Response:
    response: Response = await call_next(request)  # type: ignore[operator]
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    return response


app.include_router(health.router)
app.include_router(contracts.router, prefix="/api/v1")
app.include_router(conversations.router, prefix="/api/v1")
