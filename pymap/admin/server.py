
from __future__ import annotations

from asyncio import AbstractEventLoop

from grpclib.server import Server as _Server

__all__ = ['Server']


class Server(_Server):
    """The :class:`~grpclib.server.Server` class included with :mod:`grpclib`
    has typing issues due to some missing methods. These methods do not seem to
    be part of its public API, so they should be implemented to simply raise
    exceptions.

    Note:
        If this is fixed upstream, this class should be removed.

    """

    def get_loop(self) -> AbstractEventLoop:
        raise NotImplementedError()

    def is_serving(self) -> bool:
        raise NotImplementedError()

    async def serve_forever(self) -> None:
        raise NotImplementedError()

    async def start_serving(self) -> None:
        raise NotImplementedError()
