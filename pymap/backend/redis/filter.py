
from __future__ import annotations

import uuid
from typing import Optional, Tuple, Sequence, List

from aioredis import Redis  # type: ignore

from ._util import WatchMultiExec
from .keys import NamespaceKeys, FilterKeys
from pymap.filter import EntryPointFilterSet

__all__ = ['FilterSet']


class FilterSet(EntryPointFilterSet[bytes]):

    _active_name = b''

    def __init__(self, redis: Redis, ns_keys: NamespaceKeys) -> None:
        super().__init__('sieve', bytes)
        self._redis = redis
        self._keys = FilterKeys(ns_keys)

    @classmethod
    def _get_random_key(cls) -> bytes:
        return uuid.uuid4().hex.encode('ascii')

    async def put(self, name: str, value: bytes) -> None:
        keys = self._keys
        name_bytes = name.encode('utf-8')
        key = self._get_random_key()
        pipe = self._redis.pipeline()
        pipe.unwatch()
        pipe.hset(keys.data, key, value)
        pipe.hset(keys.names, name_bytes, key)
        await pipe.execute()

    async def delete(self, name: str) -> None:
        keys = self._keys
        name_bytes = name.encode('utf-8')
        txn = WatchMultiExec(self._redis, keys.names)
        async for pipe, multi in txn.execute():
            pipe.hmget(keys.names, name_bytes, self._active_name)
            _, _, (name_key, active_key) = await pipe.execute()
            if name_key is None:
                raise KeyError(name)
            elif name_key == active_key:
                raise ValueError(name)
            multi.hdel(keys.data, name_key)
            multi.hdel(keys.names, name_bytes)

    async def rename(self, before_name: str, after_name: str) -> None:
        keys = self._keys
        before_name_bytes = before_name.encode('utf-8')
        after_name_bytes = after_name.encode('utf-8')
        txn = WatchMultiExec(self._redis, keys.names)
        async for pipe, multi in txn.execute():
            pipe.hmget(keys.names, before_name_bytes, after_name_bytes)
            _, _, (before_name_key, after_name_key) = await pipe.execute()
            if before_name_key is None:
                raise KeyError(before_name)
            elif after_name_key is not None:
                raise KeyError(after_name)
            multi.hdel(keys.names, before_name_bytes)
            multi.hset(keys.names, after_name_bytes, before_name_key)

    async def clear_active(self) -> None:
        keys = self._keys
        pipe = self._redis.pipeline()
        pipe.unwatch()
        pipe.hdel(keys.names, self._active_name)
        await pipe.execute()

    async def set_active(self, name: str) -> None:
        keys = self._keys
        name_bytes = name.encode('utf-8')
        txn = WatchMultiExec(self._redis, keys.names)
        async for pipe, multi in txn.execute():
            pipe.hget(keys.names, name_bytes)
            _, _, name_key = await pipe.execute()
            if name_key is None:
                raise KeyError(name)
            multi.hset(keys.names, self._active_name, name_key)

    async def get(self, name: str) -> bytes:
        keys = self._keys
        name_bytes = name.encode('utf-8')
        pipe = self._redis.pipeline()
        pipe.unwatch()
        pipe.hget(keys.names, name_bytes)
        _, name_key = await pipe.execute()
        if name_key is None:
            raise KeyError(name)
        value = await self._redis.hget(keys.data, name_key)
        if value is None:
            raise KeyError(name)
        return value

    async def get_active(self) -> Optional[bytes]:
        keys = self._keys
        pipe = self._redis.pipeline()
        pipe.unwatch()
        pipe.hget(keys.names, self._active_name)
        _, active_key = await pipe.execute()
        if active_key is None:
            return None
        value = await self._redis.hget(keys.data, active_key)
        if value is None:
            return None
        return value

    async def get_all(self) -> Tuple[Optional[str], Sequence[str]]:
        keys = self._keys
        pipe = self._redis.pipeline()
        pipe.unwatch()
        pipe.hgetall(keys.names)
        _, sieve_names = await pipe.execute()
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
