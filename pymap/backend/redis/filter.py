
from __future__ import annotations

from collections.abc import Sequence
from typing import Optional

from aioredis import Redis, ReplyError

from .keys import NamespaceKeys, FilterKeys
from .scripts.filter import FilterScripts
from pymap.filter import PluginFilterSet
from pymap.parsing.specials import ObjectId

__all__ = ['FilterSet']

_scripts = FilterScripts()


class FilterSet(PluginFilterSet[bytes]):

    _active_name = b''

    def __init__(self, redis: Redis, ns_keys: NamespaceKeys) -> None:
        super().__init__(None, bytes)
        self._redis = redis
        self._keys = FilterKeys(ns_keys)

    async def put(self, name: str, value: bytes) -> None:
        keys = self._keys
        name_bytes = name.encode('utf-8')
        key = ObjectId.random(b'S').value
        pipe = self._redis.pipeline()
        pipe.hset(keys.data, key, value)
        pipe.hset(keys.names, name_bytes, key)
        await pipe.execute()

    async def delete(self, name: str) -> None:
        try:
            await _scripts.delete(self._redis, self._keys,
                                  name=name.encode('utf-8'),
                                  active_name=self._active_name)
        except ReplyError as exc:
            if 'filter not found' in str(exc):
                raise KeyError(name) from exc
            elif 'filter is active' in str(exc):
                raise ValueError(name) from exc
            raise

    async def rename(self, before_name: str, after_name: str) -> None:
        try:
            await _scripts.rename(self._redis, self._keys,
                                  before_name=before_name.encode('utf-8'),
                                  after_name=after_name.encode('utf-8'))
        except ReplyError as exc:
            if 'filter not found' in str(exc):
                raise KeyError(before_name) from exc
            elif 'filter already exists' in str(exc):
                raise KeyError(after_name) from exc
            raise

    async def clear_active(self) -> None:
        keys = self._keys
        await self._redis.hdel(keys.names, self._active_name)

    async def set_active(self, name: str) -> None:
        try:
            await _scripts.set_active(self._redis, self._keys,
                                      name=name.encode('utf-8'),
                                      active_name=self._active_name)
        except ReplyError as exc:
            if 'filter not found' in str(exc):
                raise KeyError(name) from exc
            raise

    async def get(self, name: str) -> bytes:
        try:
            return await _scripts.get(self._redis, self._keys,
                                      name=name.encode('utf-8'))
        except ReplyError as exc:
            if 'filter not found' in str(exc):
                raise KeyError(name) from exc
            raise

    async def get_active(self) -> Optional[bytes]:
        try:
            return await _scripts.get(self._redis, self._keys,
                                      name=self._active_name)
        except ReplyError as exc:
            if 'filter not found' in str(exc):
                return None
            raise

    async def get_all(self) -> tuple[Optional[str], Sequence[str]]:
        keys = self._keys
        filter_names = await self._redis.hgetall(keys.names)
        active_key: Optional[bytes] = filter_names.get(self._active_name)
        active_name: Optional[str] = None
        names: list[str] = []
        for name, key in filter_names.items():
            if name != self._active_name:
                name_str = name.decode('utf-8')
                names.append(name_str)
                if key == active_key:
                    active_name = name_str
        return active_name, names
