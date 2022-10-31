
from __future__ import annotations

import hashlib
import os.path
from collections.abc import Sequence
from contextlib import closing
from typing import final, Generic, TypeAlias, TypeVar, Any

import msgpack
from redis.asyncio import Redis
from redis.exceptions import NoScriptError
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
        # Redis docs specify using SHA1 here:
        return hashlib.sha1(data).hexdigest(), data  # nosec

    def _convert(self, ret: Any) -> _RetT:
        converted: _RetT = ret
        return converted

    @final
    def _pack(self, val: Any) -> bytes:
        packed: bytes = msgpack.packb(val)
        return packed

    def _maybe_int(self, val: bytes) -> int | None:
        if val == b'':
            return None
        else:
            return int(val)

    async def eval(self, redis: Redis[bytes], keys: Sequence[bytes],
                   args: Sequence[_Val]) -> _RetT:
        """Run the script.

        Notes:
            This attempts the EVALSHA command first, then falls back to EVAL if
            a NOSCRIPT error is returned.

        Raises:
            :class:`~asyncio.ResponseError`

        """
        num_keys = len(keys)
        try:
            ret = await redis.evalsha(
                self._sha, num_keys, *keys, *args)  # type: ignore
        except NoScriptError:
            self._sha, data = self._load()
            ret = await redis.eval(
                data, num_keys, *keys, *args)  # type: ignore
        return self._convert(ret)
