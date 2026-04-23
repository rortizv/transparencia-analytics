from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from transparencia.api.routers import contracts, health
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

app.include_router(health.router)
app.include_router(contracts.router, prefix="/api/v1")
