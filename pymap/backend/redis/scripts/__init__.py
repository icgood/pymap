
from __future__ import annotations

import hashlib
import os.path
from collections.abc import Sequence
from contextlib import closing
from typing import Generic, TypeVar, Any, Union, Optional

import msgpack
from aioredis import Redis, ReplyError
from pkg_resources import resource_stream

__all__ = ['ScriptBase']

_Val = Union[int, bytes]
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

    def _maybe_int(self, val: bytes) -> Optional[int]:
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
            :class:`~asyncio.ReplyError`

        """
        try:
            ret = await redis.evalsha(self._sha, keys, args)
        except ReplyError as exc:
            if 'NOSCRIPT' in str(exc):
                self._sha, data = self._load()
                ret = await redis.eval(data, keys, args)
            else:
                raise
        return self._convert(ret)
