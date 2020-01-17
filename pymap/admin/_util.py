
from __future__ import annotations

from contextlib import AsyncExitStack
from typing import TypeVar

from pymap.context import connection_exit

__all__ = ['exit_context']

_F = TypeVar('_F')


def exit_context(func: _F) -> _F:
    async def deco(*args, **kwargs):
        async with AsyncExitStack() as stack:
            connection_exit.set(stack)
            return await func(*args, **kwargs)
    return deco  # type: ignore
