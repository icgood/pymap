
from __future__ import annotations

import asyncio
from typing import Any, Tuple, Optional, Collection, AsyncIterator

from aioredis import Redis, MultiExecError, WatchVariableError  # type: ignore
from aioredis.commands.transaction import Pipeline, MultiExec  # type: ignore

__all__ = ['WatchMultiExec']


class WatchMultiExec:

    def __init__(self, redis: Redis, *watch_keys: bytes) -> None:
        super().__init__()
        self._redis = redis
        self._watch_keys = watch_keys
        self._results: Optional[Collection[Any]] = None

    @classmethod
    async def _check_errors(cls, multi: MultiExec) -> bool:
        # Prevents warning about exception never being retrieved.
        errors = await asyncio.gather(*multi._results, return_exceptions=True)
        return any(not isinstance(exc, WatchVariableError) for exc in errors)

    async def execute(self) -> AsyncIterator[Tuple[Pipeline, MultiExec]]:
        redis = self._redis
        watch_keys = self._watch_keys
        while True:
            pipe = redis.pipeline()
            pipe.unwatch()
            if watch_keys:
                pipe.watch(*watch_keys)
            multi = redis.multi_exec()
            yield (pipe, multi)
            try:
                self._results = await multi.execute()
            except MultiExecError:
                if await self._check_errors(multi):
                    raise
            else:
                break

    @property
    def results(self) -> Collection[Any]:
        if self._results is None:
            raise TypeError('Loop not yet iterated')
        return self._results
