
from __future__ import annotations

import asyncio
from contextlib import suppress

from aioredis import Redis, RedisError, WatchVariableError  # type: ignore

__all__ = ['reset', 'check_errors']


async def reset(redis: Redis) -> Redis:
    with suppress(RedisError):
        await redis.unwatch()
    return redis


async def check_errors(multi: Redis) -> bool:
    # Prevents warning about exception never being retrieved.
    errors = await asyncio.gather(*multi._results, return_exceptions=True)
    return any(not isinstance(exc, WatchVariableError) for exc in errors)
