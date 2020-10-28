
from __future__ import annotations

import asyncio
import sys
from argparse import ArgumentParser, SUPPRESS
from asyncio import CancelledError
from datetime import datetime, timedelta, timezone
from secrets import token_bytes
from ssl import SSLContext
from typing import Optional, Sequence, Awaitable

from grpclib.events import listen, RecvRequest
from grpclib.server import Server
from pymap.interfaces.backend import BackendInterface, ServiceInterface
from pymapadmin import is_compatible, __version__ as server_version
from pymapadmin.local import get_admin_socket

from .errors import get_incompatible_version_error
from .handlers import handlers
from .token import get_admin_token

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

    _admin_token: Optional[bytes] = None

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        group = parser.add_argument_group('admin service')
        group.add_argument('--admin-host', action='append', metavar='IFACE',
                           help='the network interface to listen on')
        group.add_argument('--admin-port', metavar='NUM',
                           help='the port or service name to listen on')
        group.add_argument('--no-admin-token', action='store_true',
                           help='disable the admin token')
        group.add_argument('--admin-token-duration', metavar='SEC', type=int,
                           help=SUPPRESS)

    def _init_admin_token(self) -> None:
        if not self.config.args.no_admin_token:
            expiration: Optional[datetime] = None
            if self.config.args.admin_token_duration:
                duration_sec: int = self.config.args.admin_token_duration
                duration = timedelta(seconds=duration_sec)
                expiration = datetime.now(tz=timezone.utc) + duration
            self._admin_token = token_bytes()
            token = get_admin_token(self._admin_token, expiration)
            print(f'PYMAP_ADMIN_TOKEN={token.serialize()}', file=sys.stderr)

    async def _check_version(self, event: RecvRequest) -> None:
        client_version = event.metadata['client-version']
        if isinstance(client_version, bytes):
            client_version = client_version.decode('ascii')
        if not is_compatible(client_version, server_version):
            raise get_incompatible_version_error(
                client_version, server_version)

    async def start(self) -> Awaitable:
        self._init_admin_token()
        backend = self.backend
        host: Optional[str] = self.config.args.admin_host
        port: Optional[int] = self.config.args.admin_port
        ssl = self.config.ssl_context
        servers = [await self._start_local(backend)]
        if host or port:
            servers += [await self._start(backend, host, port, ssl)]
        return asyncio.create_task(self._run(servers))

    def _new_server(self, backend: BackendInterface) -> Server:
        server = Server([handler(backend, self._admin_token)
                         for _, handler in handlers])
        listen(server, RecvRequest, self._check_version)
        return server

    async def _start_local(self, backend: BackendInterface) -> Server:
        server = self._new_server(backend)
        path = get_admin_socket(mkdir=True)
        await server.start(path=path)
        return server

    async def _start(self, backend: BackendInterface, host: Optional[str],
                     port: Optional[int], ssl: Optional[SSLContext]) -> Server:
        server = self._new_server(backend)
        await server.start(host=host, port=port, ssl=ssl, reuse_address=True)
        return server

    async def _run(self, servers: Sequence[Server]) -> None:
        try:
            for server in servers:
                await server.wait_closed()
        except CancelledError:
            for server in servers:
                server.close()
                await server.wait_closed()
