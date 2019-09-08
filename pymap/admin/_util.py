
from __future__ import annotations

from contextlib import AsyncExitStack

from pymap.context import connection_exit

__all__ = ['exit_context']


def exit_context(func):
    async def deco(*args, **kwargs):
        async with AsyncExitStack() as stack:
            connection_exit.set(stack)
            return await func(*args, **kwargs)
    return deco
