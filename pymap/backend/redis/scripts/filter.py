
from __future__ import annotations

from typing import Final

from aioredis import Redis

from . import ScriptBase
from ..keys import FilterKeys

__all__ = ['FilterScripts']


class FilterScripts:

    def __init__(self) -> None:
        super().__init__()
        self.get: Final = FilterGet()
        self.set_active: Final = FilterSetActive()
        self.delete: Final = FilterDelete()
        self.rename: Final = FilterRename()


class FilterGet(ScriptBase[bytes]):

    def __init__(self) -> None:
        super().__init__('filter_get')

    async def __call__(self, redis: Redis, fl_keys: FilterKeys, *,
                       name: bytes) -> bytes:
        keys = [fl_keys.names, fl_keys.data]
        args = [name]
        return await self.eval(redis, keys, args)


class FilterSetActive(ScriptBase[None]):

    def __init__(self) -> None:
        super().__init__('filter_set_active')

    async def __call__(self, redis: Redis, fl_keys: FilterKeys, *,
                       name: bytes, active_name: bytes) -> None:
        keys = [fl_keys.names]
        args = [name, active_name]
        return await self.eval(redis, keys, args)


class FilterDelete(ScriptBase[None]):

    def __init__(self) -> None:
        super().__init__('filter_delete')

    async def __call__(self, redis: Redis, fl_keys: FilterKeys, *,
                       name: bytes, active_name: bytes) -> None:
        keys = [fl_keys.names, fl_keys.data]
        args = [name, active_name]
        return await self.eval(redis, keys, args)


class FilterRename(ScriptBase[None]):

    def __init__(self) -> None:
        super().__init__('filter_rename')

    async def __call__(self, redis: Redis, fl_keys: FilterKeys, *,
                       before_name: bytes, after_name: bytes) -> None:
        keys = [fl_keys.names]
        args = [before_name, after_name]
        return await self.eval(redis, keys, args)
