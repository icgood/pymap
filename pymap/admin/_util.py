
from __future__ import annotations

from contextlib import AsyncExitStack
from functools import wraps
from typing import cast, TypeVar, Callable

from pymap.context import connection_exit

__all__ = ['exit_context']

_F = TypeVar('_F', bound=Callable)


def exit_context(func: _F) -> _F:
    @wraps(func)
    async def deco(*args, **kwargs):
        async with AsyncExitStack() as stack:
            connection_exit.set(stack)
            return await func(*args, **kwargs)
    return cast(_F, deco)
