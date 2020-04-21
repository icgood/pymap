
from __future__ import annotations

import asyncio
from argparse import ArgumentParser
from asyncio import Task, CancelledError
from typing import Any, Callable, Sequence

from grpclib.server import Server
from pkg_resources import iter_entry_points, DistributionNotFound
from pymap.config import IMAPConfig
from pymap.interfaces.backend import BackendInterface, ServiceInterface

__all__ = ['AdminService']

_HandlerType = Callable[[BackendInterface], Any]


class AdminService(ServiceInterface):  # pragma: no cover
    """A pymap service implemented using a `grpc <https://grpc.io/>`_ server
    to perform admin functions on a running backend.

    """

    def __init__(self, servers: Sequence[Server]) -> None:
        super().__init__()
        self._servers = servers
        self._task = asyncio.create_task(self._run())

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        group = parser.add_argument_group('admin service')
        group.add_argument('--admin-host', metavar='HOST', dest='admin_host',
                           action='append', help='host to listen on')
        group.add_argument('--admin-port', metavar='PORT', dest='admin_port',
                           type=int, default=9090, help='port to listen on')

    @classmethod
    async def start(cls, backend: BackendInterface,
                    config: IMAPConfig) -> AdminService:
        config = backend.config
        hosts: Sequence[str] = config.args.admin_host
        port: int = config.args.admin_port
        handler_types = cls._get_handler_types()
        if not hosts:
            hosts = ['127.0.0.1']
        servers = [await cls._start(handler_types, backend, host, port)
                   for host in hosts]
        return cls(servers)

    @classmethod
    def _get_handler_types(cls) -> Sequence[_HandlerType]:
        handler_types = []
        for entry_point in iter_entry_points('pymap.admin.handlers'):
            try:
                handler_cls = entry_point.load()
            except DistributionNotFound:
                pass  # optional dependencies not installed
            else:
                handler_types.append(handler_cls)
        return handler_types

    @classmethod
    def _new_server(cls, handler_types: Sequence[_HandlerType],
                    backend: BackendInterface) -> Server:
        handlers = [handler(backend) for handler in handler_types]
        return Server(handlers)

    @classmethod
    async def _start(cls, handler_types: Sequence[_HandlerType],
                     backend: BackendInterface,
                     host: str, port: int) -> Server:
        server = cls._new_server(handler_types, backend)
        await server.start(host=host, port=port, reuse_address=True)
        return server

    @property
    def task(self) -> Task:
        return self._task

    async def _run(self) -> None:
        servers = self._servers
        try:
            for server in servers:
                await server.wait_closed()
        except CancelledError:
            for server in servers:
                server.close()
                await server.wait_closed()
