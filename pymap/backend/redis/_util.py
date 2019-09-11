
from __future__ import annotations

import asyncio

from aioredis import Redis, WatchVariableError  # type: ignore

__all__ = ['unwatch_pipe', 'watch_pipe', 'check_errors']


def unwatch_pipe(redis: Redis) -> Redis:
    pipe = redis.pipeline()
    pipe.unwatch()
    return pipe


def watch_pipe(redis: Redis, *watch: bytes) -> Redis:
    pipe = unwatch_pipe(redis)
    pipe.watch(*watch)
    return pipe


async def check_errors(multi: Redis) -> bool:
    # Prevents warning about exception never being retrieved.
    errors = await asyncio.gather(*multi._results, return_exceptions=True)
    return any(not isinstance(exc, WatchVariableError) for exc in errors)
