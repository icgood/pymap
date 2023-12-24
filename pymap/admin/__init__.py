
from __future__ import annotations

import asyncio
import shlex
import sys
from argparse import ArgumentParser, SUPPRESS
from asyncio import Task, CancelledError
from collections.abc import Mapping, Sequence
from contextlib import AsyncExitStack
from datetime import datetime, timedelta, timezone
from ssl import SSLContext
from typing import Any

from grpclib.events import listen, RecvRequest
from grpclib.health.check import ServiceStatus
from grpclib.health.service import Health
from grpclib.server import Server
from pymap.context import cluster_metadata
from pymap.interfaces.backend import ServiceInterface
from pymapadmin import is_compatible
from pymapadmin.__about__ import __version__ as server_version
from pymapadmin.local import socket_file, token_file

from .errors import get_incompatible_version_error
from .handlers import handlers
from .typing import Handler

__all__ = ['AdminService']


class _HealthService:
    def __init__(self, name: str) -> None:
        self._name = name

    def __mapping__(self) -> Mapping[str, Any]:
        return {f'/{self._name}/': None}


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
        group.add_argument('--admin-path', action=socket_file.add_action,
                           help=SUPPRESS)
        group.add_argument('--admin-host', action='append', metavar='IFACE',
                           help='the network interface to listen on')
        group.add_argument('--admin-port', metavar='NUM', type=int,
                           default=50051, help='the port to listen on')
        group.add_argument('--admin-token-file', action=token_file.add_action,
                           help=SUPPRESS)
        group.add_argument('--admin-token-duration', metavar='SEC', type=int,
                           help=SUPPRESS)

    def _init_admin_token(self) -> None:
        expiration: datetime | None = None
        if self.config.args.admin_token_duration:
            duration_sec: int = self.config.args.admin_token_duration
            duration = timedelta(seconds=duration_sec)
            expiration = datetime.now(tz=timezone.utc) + duration
        admin_key = self.config.admin_key
        token = self.backend.login.tokens.get_admin_token(
            admin_key, expiration=expiration)
        if token is not None:
            self._write_admin_token(token)
            print(f'PYMAP_ADMIN_TOKEN={shlex.quote(token)}', file=sys.stderr)
        if admin_key is not None:
            cluster_metadata.get().local['admin'] = admin_key

    def _write_admin_token(self, admin_token: str) -> None:
        try:
            path = token_file.get_temp(mkdir=True)
            path.write_text(admin_token)
        except OSError:
            pass

    async def _check_version(self, event: RecvRequest) -> None:
        client_version = event.metadata.get('client-version')
        if client_version is not None:
            if isinstance(client_version, bytes):
                client_version = client_version.decode('ascii')
            if not is_compatible(client_version, server_version):
                raise get_incompatible_version_error(
                    client_version, server_version)

    def _get_health(self) -> Handler:
        backend_status = ServiceStatus()
        self.backend.status.register(backend_status.set)
        return Health({_HealthService('pymap.backend'): [backend_status]})

    async def start(self, stack: AsyncExitStack) -> None:
        self._init_admin_token()
        backend = self.backend
        host: str | None = self.config.args.admin_host
        port: int | None = self.config.args.admin_port
        server_handlers: list[Handler] = [self._get_health()]
        server_handlers.extend(handler(backend)
                               for handler in handlers.values())
        ssl = self.config.ssl_context
        local_task = await self._start_local(server_handlers)
        remote_task = await self._start(server_handlers, host, port, ssl)
        stack.callback(local_task.cancel)
        stack.callback(remote_task.cancel)

    def _new_server(self, server_handlers: Sequence[Handler]) -> Server:
        server = Server(server_handlers)
        listen(server, RecvRequest, self._check_version)
        return server

    async def _start_local(self, server_handlers: Sequence[Handler]) \
            -> Task[None]:
        server = self._new_server(server_handlers)
        path = str(socket_file.get_temp(mkdir=True))
        await server.start(path=path)
        return asyncio.create_task(self._run(server))

    async def _start(self, server_handlers: Sequence[Handler],
                     host: str | None, port: int | None,
                     ssl: SSLContext | None) -> Task[None]:
        server = self._new_server(server_handlers)
        await server.start(host=host, port=port, ssl=ssl, reuse_address=True)
        return asyncio.create_task(self._run(server))

    async def _run(self, server: Server) -> None:
        try:
            await server.wait_closed()
        except CancelledError:
            server.close()
            await server.wait_closed()
            raise
