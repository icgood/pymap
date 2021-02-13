
from __future__ import annotations

from abc import abstractmethod
from collections.abc import Mapping
from typing import Protocol

from grpclib.const import Handler as _Handler

__all__ = ['Handler']


class Handler(Protocol):
    """Defines the protocol for :class:`~grpclib.server.Server` handlers. This
    can be removed if ``grpclib._typing.IServable`` becomes public API.

    """

    @abstractmethod
    def __mapping__(self) -> Mapping[str, _Handler]:
        ...
