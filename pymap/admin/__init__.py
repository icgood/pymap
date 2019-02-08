
import asyncio
import os
import os.path
import tempfile
from argparse import ArgumentParser
from asyncio import Task, AbstractServer, CancelledError
from typing import Optional, Sequence

from grpclib.server import Server  # type: ignore
from pymap.config import IMAPConfig
from pymap.interfaces.backend import BackendInterface, ServiceInterface

from .handlers import AdminHandlers

__all__ = ['AdminService']


class AdminService(ServiceInterface):
    """A pymap service implemented using a `grpc <https://grpc.io/>`_ server
    to perform admin functions on a running backend.

    """

    def __init__(self, path: str, server: AbstractServer) -> None:
        super().__init__()
        self._path = path
        self._server = server
        self._task = asyncio.create_task(self._run())

    @classmethod
    def get_socket_paths(cls) -> Sequence[str]:
        """Return the prioritized list of locations to create or check for the
        UNIX socket file listening for admin requests.

        """
        basename = 'pymap-admin.sock'
        return [os.path.join(os.sep, 'var', 'run', basename),
                os.path.join(tempfile.gettempdir(), basename)]

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        group = parser.add_argument_group('admin service')
        group.add_argument('--socket', metavar='PATH', dest='admin_sock',
                           help='path to socket file')
        group.add_argument('--no-filter', action='store_true',
                           help='do not filter appended messages')

    @classmethod
    async def start(cls, backend: BackendInterface,
                    config: IMAPConfig) -> 'AdminService':
        config = backend.config
        path: Optional[str] = config.args.admin_sock
        handlers = AdminHandlers(backend)
        server = Server([handlers], loop=asyncio.get_event_loop())
        path = await cls._start(path, server)
        return cls(path, server)

    @classmethod
    async def _start(cls, path: Optional[str], server: Server) -> str:
        if path:
            await server.start(path=path)
            return path
        else:
            last_exc: Optional[OSError] = None
            for path in cls.get_socket_paths():
                try:
                    await server.start(path=path)
                    return path
                except OSError as exc:
                    last_exc = exc
            raise RuntimeError('Failed starting admin service') from last_exc

    @property
    def task(self) -> 'Task[None]':
        return self._task

    def _unlink_path(self) -> None:
        try:
            os.unlink(self._path)
        except OSError:
            pass

    async def _run(self) -> None:
        server = self._server
        try:
            await server.wait_closed()
        except CancelledError:
            server.close()
            await server.wait_closed()
        finally:
            self._unlink_path()
