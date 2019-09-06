
from __future__ import annotations

import asyncio
import uuid
from typing import Optional, Tuple, Sequence, List

from aioredis import Redis, MultiExecError, WatchVariableError  # type: ignore

from pymap.filter import EntryPointFilterSet

__all__ = ['FilterSet']


async def _check_errors(multi) -> bool:
    # Prevents warning about exception never being retrieved.
    errors = await asyncio.gather(*multi._results, return_exceptions=True)
    return any(not isinstance(exc, WatchVariableError) for exc in errors)


class FilterSet(EntryPointFilterSet[bytes]):

    _active_name = b''

    def __init__(self, redis: Redis, prefix: bytes) -> None:
        super().__init__('sieve', bytes)
        self._redis = redis
        self._prefix = prefix

    @classmethod
    def _get_random_key(cls) -> bytes:
        return uuid.uuid4().hex.encode('ascii')

    async def put(self, name: str, value: bytes) -> None:
        redis = self._redis
        prefix = self._prefix
        name_bytes = name.encode('utf-8')
        key = self._get_random_key()
        await redis.hset(prefix + b':sieve-data', key, value)
        await redis.hset(prefix + b':sieve', name_bytes, key)

    async def delete(self, name: str) -> None:
        redis = self._redis
        prefix = self._prefix
        name_bytes = name.encode('utf-8')
        while True:
            await redis.watch(prefix + b':sieve')
            name_key, active_key = await redis.hmget(
                prefix + b':sieve', name_bytes, self._active_name)
            if name_key is None:
                await redis.unwatch()
                raise KeyError(name)
            elif name_key == active_key:
                await redis.unwatch()
                raise ValueError(name)
            multi = redis.multi_exec()
            multi.hdel(prefix + b':sieve-data', name_key)
            multi.hdel(prefix + b':sieve', name_bytes)
            try:
                await multi.execute()
            except MultiExecError:
                if await _check_errors(multi):
                    raise
            else:
                break

    async def rename(self, before_name: str, after_name: str) -> None:
        redis = self._redis
        prefix = self._prefix
        before_name_bytes = before_name.encode('utf-8')
        after_name_bytes = after_name.encode('utf-8')
        while True:
            await redis.watch(prefix + b':sieve')
            before_name_key, after_name_key = await redis.hmget(
                prefix + b':sieve', before_name_bytes, after_name_bytes)
            if before_name_key is None:
                await redis.unwatch()
                raise KeyError(before_name)
            elif after_name_key is not None:
                await redis.unwatch()
                raise KeyError(after_name)
            multi = redis.multi_exec()
            multi.hdel(prefix + b':sieve', before_name_bytes)
            multi.hset(prefix + b':sieve', after_name_bytes, before_name_key)
            try:
                await multi.execute()
            except MultiExecError:
                if await _check_errors(multi):
                    raise
            else:
                break

    async def set_active(self, name: Optional[str]) -> None:
        redis = self._redis
        prefix = self._prefix
        if name is None:
            await redis.hdel(prefix + b':sieve', self._active_name)
            return
        else:
            name_bytes = name.encode('utf-8')
            while True:
                await redis.watch(prefix + b':sieve')
                name_key = await redis.hget(prefix + b':sieve', name_bytes)
                if name_key is None:
                    await redis.unwatch()
                    raise KeyError(name)
                multi = redis.multi_exec()
                multi.hset(prefix + b':sieve', self._active_name, name_key)
                try:
                    await multi.execute()
                except MultiExecError:
                    if await _check_errors(multi):
                        raise
                else:
                    break

    async def get(self, name: str) -> bytes:
        redis = self._redis
        prefix = self._prefix
        name_bytes = name.encode('utf-8')
        name_key = await redis.hget(prefix + b':sieve', name_bytes)
        if name_key is None:
            raise KeyError(name)
        value = await redis.hget(prefix + b':sieve-data', name_key)
        if value is None:
            raise KeyError(name)
        return value

    async def get_active(self) -> Optional[bytes]:
        redis = self._redis
        prefix = self._prefix
        active_key = await redis.hget(prefix + b':sieve', self._active_name)
        if active_key is None:
            return None
        value = await redis.hget(prefix + b':sieve-data', active_key)
        if value is None:
            return None
        return value

    async def get_all(self) -> Tuple[Optional[str], Sequence[str]]:
        redis = self._redis
        prefix = self._prefix
        sieve_names = await redis.hgetall(prefix + b':sieve')
        active_key: Optional[bytes] = sieve_names.get(self._active_name)
        active_name: Optional[str] = None
        names: List[str] = []
        for name, key in sieve_names.items():
            if name != self._active_name:
                name_str = name.decode('utf-8')
                names.append(name_str)
                if key == active_key:
                    active_name = name_str
        return active_name, names
