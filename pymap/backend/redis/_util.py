
from __future__ import annotations

import asyncio
from contextlib import suppress

from aioredis import Redis, WatchVariableError  # type: ignore

__all__ = ['reset', 'check_errors']


async def reset(redis: Redis) -> Redis:
    with suppress(Exception):
        await redis.discard()
    return redis


async def check_errors(multi: Redis) -> bool:
    # Prevents warning about exception never being retrieved.
    errors = await asyncio.gather(*multi._results, return_exceptions=True)
    return any(not isinstance(exc, WatchVariableError) for exc in errors)
