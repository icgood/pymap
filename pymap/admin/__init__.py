
from __future__ import annotations

import asyncio
from argparse import ArgumentParser
from asyncio import CancelledError
from ssl import SSLContext
from typing import Optional, Tuple, Sequence, Awaitable
from urllib.parse import urlparse

from grpclib.server import Server
from pymap.interfaces.backend import BackendInterface, ServiceInterface
from pymapadmin.local import get_admin_socket

from .handlers import handlers

__all__ = ['AdminService']


class AdminService(ServiceInterface):  # pragma: no cover
    """A pymap service implemented using a `grpc <https://grpc.io/>`_ server
    to perform admin functions on a running backend.

    This service can be exposed in *private* or *public* mode. Private mode
    does not use SSL/TLS encryption and authentication is not required, so it
    should be appropriately firewalled. Public mode requires both SSL/TLS
    encryption and the client provide credentials for the user being
    operated on, e.g. a user can change their own password but cannot change
    another user's password.

    The `pymap-admin <https://github.com/icgood/pymap-admin>`_ CLI may be used
    to interact with the admin service and serves as a reference client
    implementation.

    """

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        group = parser.add_argument_group('admin service')
        group.add_argument('--admin-private', metavar='HOST',
                           action='append', default=[],
                           help='private host:port to listen on')
        group.add_argument('--admin-public', metavar='HOST',
                           action='append', default=[],
                           help='public host:port to listen on')

    async def start(self) -> Awaitable:
        backend = self.backend
        private_hosts: Sequence[str] = self.config.args.admin_private
        public_hosts: Sequence[str] = self.config.args.admin_public
        ssl = self.config.ssl_context
        servers = [await self._start_local(backend)]
        servers += [await self._start(backend, False, host, None)
                    for host in private_hosts]
        servers += [await self._start(backend, True, host, ssl)
                    for host in public_hosts]
        return asyncio.create_task(self._run(servers))

    @classmethod
    def _new_server(cls, backend: BackendInterface, public: bool) -> Server:
        return Server([handler(backend, public) for _, handler in handlers])

    @classmethod
    async def _start_local(cls, backend: BackendInterface) -> Server:
        server = cls._new_server(backend, False)
        path = get_admin_socket(mkdir=True)
        await server.start(path=path)
        return server

    @classmethod
    async def _start(cls, backend: BackendInterface, public: bool,
                     host: str, ssl: Optional[SSLContext]) -> Server:
        server = cls._new_server(backend, public)
        host, port = cls._parse(host)
        await server.start(host=host, port=port, ssl=ssl, reuse_address=True)
        return server

    @classmethod
    def _parse(cls, host: str) -> Tuple[str, Optional[int]]:
        parsed = urlparse(host)
        if parsed.hostname:
            return parsed.hostname, parsed.port
        parsed = urlparse(f'//{host}')
        if parsed.hostname:
            return parsed.hostname, parsed.port
        raise ValueError(host)

    @classmethod
    async def _run(cls, servers: Sequence[Server]) -> None:
        try:
            for server in servers:
                await server.wait_closed()
        except CancelledError:
            for server in servers:
                server.close()
                await server.wait_closed()
