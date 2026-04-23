from contextlib import asynccontextmanager
from typing import AsyncIterator

import psycopg
from psycopg_pool import AsyncConnectionPool

from transparencia.config import settings

_pool: AsyncConnectionPool | None = None


async def init_pool() -> None:
    global _pool
    _pool = AsyncConnectionPool(conninfo=settings.database_url, open=False)
    await _pool.open()


async def close_pool() -> None:
    if _pool:
        await _pool.close()


@asynccontextmanager
async def get_conn() -> AsyncIterator[psycopg.AsyncConnection]:
    if _pool is None:
        raise RuntimeError("Database pool not initialized")
    async with _pool.connection() as conn:
        yield conn
