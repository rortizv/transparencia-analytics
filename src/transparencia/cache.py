"""
Simple in-process LRU + TTL cache for expensive read-only queries.

Usage:
    from transparencia.cache import cache

    @cache(ttl=300)
    async def my_handler(param: str) -> list[dict]:
        ...

The cache key is derived from the function name and all positional/keyword
arguments. Entries expire after `ttl` seconds (default 5 min).
Max 256 entries; LRU eviction beyond that.
"""

import asyncio
import functools
import hashlib
import json
import time
from collections import OrderedDict
from typing import Any, Callable

_MAX_ENTRIES = 256


class _Cache:
    def __init__(self) -> None:
        self._store: OrderedDict[str, tuple[Any, float]] = OrderedDict()

    def _make_key(self, fn_name: str, args: tuple, kwargs: dict) -> str:
        raw = json.dumps({"fn": fn_name, "a": args, "kw": kwargs}, default=str, sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def get(self, key: str, ttl: float) -> tuple[bool, Any]:
        if key not in self._store:
            return False, None
        value, ts = self._store[key]
        if time.monotonic() - ts > ttl:
            del self._store[key]
            return False, None
        self._store.move_to_end(key)
        return True, value

    def set(self, key: str, value: Any) -> None:
        if key in self._store:
            self._store.move_to_end(key)
        self._store[key] = (value, time.monotonic())
        while len(self._store) > _MAX_ENTRIES:
            self._store.popitem(last=False)

    def invalidate_all(self) -> None:
        self._store.clear()


_cache = _Cache()


def cache(ttl: float = 300) -> Callable:
    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            key = _cache._make_key(fn.__qualname__, args, kwargs)
            hit, value = _cache.get(key, ttl)
            if hit:
                return value
            result = await fn(*args, **kwargs)
            _cache.set(key, result)
            return result
        return wrapper
    return decorator
