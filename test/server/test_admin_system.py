
from grpclib.testing import ChannelFor
from pymapadmin import __version__ as pymap_admin_version
from pymapadmin.grpc.admin_grpc import SystemStub
from pymapadmin.grpc.admin_pb2 import SUCCESS, FAILURE, \
    LoginRequest, PingRequest

from pymap import __version__ as pymap_version
from pymap.admin.handlers.system import SystemHandlers
from pymap.interfaces.backend import BackendInterface

from .base import TestBase


class TestSystemHandlers(TestBase):

    async def test_login(self, backend: BackendInterface) -> None:
        handlers = SystemHandlers(backend)
        request = LoginRequest(authcid='testuser', secret='testpass')
        async with ChannelFor([handlers]) as channel:
            stub = SystemStub(channel)
            response = await stub.Login(request)
        assert SUCCESS == response.result.code
        assert response.bearer_token

    async def test_login_failure(self, backend: BackendInterface) -> None:
        handlers = SystemHandlers(backend)
        request = LoginRequest(authcid='baduser', secret='badpass')
        async with ChannelFor([handlers]) as channel:
            stub = SystemStub(channel)
            response = await stub.Login(request)
        assert FAILURE == response.result.code
        assert 'InvalidAuth' == response.result.key
        assert not response.HasField('bearer_token')

    async def test_ping(self, backend: BackendInterface) -> None:
        handlers = SystemHandlers(backend)
        request = PingRequest()
        async with ChannelFor([handlers]) as channel:
            stub = SystemStub(channel)
            response = await stub.Ping(request)
        assert SUCCESS == response.result.code
        assert pymap_version == response.pymap_version
        assert pymap_admin_version == response.pymap_admin_version
