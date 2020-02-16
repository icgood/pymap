
from __future__ import annotations

import asyncio
from argparse import ArgumentParser
from asyncio import Task, CancelledError
from typing import Sequence

from grpclib.server import Server
from pymap.config import IMAPConfig
from pymap.interfaces.backend import BackendInterface, ServiceInterface

from .handlers import AdminHandlers

__all__ = ['AdminService']


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
        group.add_argument('--no-filter', action='store_true',
                           help='do not filter appended messages')

    @classmethod
    async def start(cls, backend: BackendInterface,
                    config: IMAPConfig) -> AdminService:
        config = backend.config
        hosts: Sequence[str] = config.args.admin_host
        port: int = config.args.admin_port
        if not hosts:
            hosts = ['127.0.0.1']
        servers = [await cls._start(backend, host, port) for host in hosts]
        return cls(servers)

    @classmethod
    def _new_server(cls, backend: BackendInterface) -> Server:
        loop = asyncio.get_event_loop()
        handlers = AdminHandlers(backend)
        return Server([handlers], loop=loop)

    @classmethod
    async def _start(cls, backend: BackendInterface,
                     host: str, port: int) -> Server:
        server = cls._new_server(backend)
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
