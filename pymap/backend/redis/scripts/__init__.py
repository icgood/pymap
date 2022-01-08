
from __future__ import annotations

import hashlib
import os.path
from collections.abc import Sequence
from contextlib import closing
from typing import Generic, TypeAlias, TypeVar, Any

import msgpack
from aioredis import Redis
from aioredis.exceptions import NoScriptError
from pkg_resources import resource_stream

__all__ = ['ScriptBase']

_Val: TypeAlias = int | bytes
_RetT = TypeVar('_RetT')


class ScriptBase(Generic[_RetT]):
    """The base class for redis scripts.

    Args:
        name: The script name, which should correspond to a ``.lua`` file.

    """

    __slots__ = ['_name', '_sha']

    def __init__(self, name: str) -> None:
        super().__init__()
        self._name = name
        self._sha, _ = self._load()

    def _load(self) -> tuple[str, bytes]:
        fname = os.path.join('lua', f'{self._name}.lua')
        with closing(resource_stream(__name__, fname)) as script:
            data = script.read()
        return hashlib.sha1(data).hexdigest(), data

    def _convert(self, ret: Any) -> _RetT:
        return ret

    def _pack(self, val: Any) -> bytes:
        return msgpack.packb(val)

    def _maybe_int(self, val: bytes) -> int | None:
        if val == b'':
            return None
        else:
            return int(val)

    async def eval(self, redis: Redis, keys: Sequence[bytes],
                   args: Sequence[_Val]) -> _RetT:
        """Run the script.

        Notes:
            This attempts the EVALSHA command first, then falls back to EVAL if
            a NOSCRIPT error is returned.

        Raises:
            :class:`~asyncio.ResponseError`

        """
        num_keys = len(keys)
        # TODO: remove after aioredis > 2.0.0
        tmp_args: list[str] = [*keys, *args]  # type: ignore
        try:
            ret = await redis.evalsha(self._sha, num_keys, *tmp_args)
        except NoScriptError:
            self._sha, data = self._load()
            ret = await redis.eval(data, num_keys, *keys, *args)
        return self._convert(ret)
