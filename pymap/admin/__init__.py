
import os
import os.path
import asyncio
from argparse import ArgumentParser
from asyncio import CancelledError
from typing_extensions import Final

from grpclib.server import Server  # type: ignore
from pymap.interfaces.backend import BackendInterface, ServiceInterface

from .handlers import GrpcHandlers

__all__ = ['AdminService']


class AdminService(ServiceInterface):
    """A pymap service implemented using a `grpc <https://grpc.io/>`_ server
    to perform admin functions on a running backend.

    """

    def __init__(self, path: str, server: Server) -> None:
        super().__init__()
        self.path: Final = path
        self.server: Final = server

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        admin = parser.add_argument_group('admin arguments')
        admin.add_argument('--admin-path', metavar='PATH',
                           help='path to POSIX socket file')

    @classmethod
    async def init(cls, backend: BackendInterface) -> 'AdminService':
        config = backend.config
        if config.args.admin_path is not None:
            path = config.args.admin_path
        else:
            pid = os.getpid()
            path = os.path.join(os.sep, 'tmp', 'pymap', f'admin-{pid}.sock')
        cls._create_dir(path)
        handlers = GrpcHandlers(backend)
        server = Server([handlers], loop=asyncio.get_event_loop())
        return cls(path, server)

    @classmethod
    def _create_dir(cls, path: str) -> None:
        try:
            dirname = os.path.dirname(path)
            os.mkdir(dirname, 0o755)
        except FileExistsError:
            pass

    def _unlink_path(self) -> None:
        try:
            os.unlink(self.path)
        except OSError:
            pass

    async def run_forever(self) -> None:
        server = self.server
        await server.start(path=self.path)
        try:
            await server.wait_closed()
        except CancelledError:
            server.close()
            await server.wait_closed()
        finally:
            self._unlink_path()
