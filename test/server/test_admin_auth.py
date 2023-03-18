
from collections.abc import Mapping

import pytest
from grpclib.testing import ChannelFor
from pymapadmin.grpc.admin_grpc import SystemStub, UserStub
from pymapadmin.grpc.admin_pb2 import SUCCESS, FAILURE, UserData, \
    LoginRequest, GetUserRequest, SetUserRequest, DeleteUserRequest

from pymap.admin.handlers.system import SystemHandlers
from pymap.admin.handlers.user import UserHandlers
from pymap.interfaces.backend import BackendInterface

from .base import TestBase


class TestAdminAuth(TestBase):

    admin_token = 'MDAwZWxvY2F0aW9uIAowMDEwaWRlbnRpZmllciAKMDAxNWNpZCByb2xlI' \
        'D0gYWRtaW4KMDAyZnNpZ25hdHVyZSDND4TS4f6mH9ty0DHCwqB0IIuk_IqIUFgse0OV' \
        'eHT7cAo'

    @pytest.fixture
    def overrides(self):
        return {'admin_key': b'testadmintoken'}

    async def test_token(self, backend: BackendInterface) -> None:
        token = await self._login(backend, 'testuser', 'testpass')
        await self._get_user(backend, token, 'testuser')
        await self._set_user(backend, token, 'testuser', 'newpass')
        await self._get_user(backend, token, 'testuser')
        await self._delete_user(backend, token, 'testuser')
        await self._get_user(backend, token, 'testuser',
                             failure_key='InvalidAuth')
        await self._get_user(backend, self.admin_token, 'testuser',
                             failure_key='UserNotFound')

    async def test_authorization(self, backend: BackendInterface) -> None:
        await self._set_user(backend, self.admin_token, 'newuser', 'newpass')
        token1 = await self._login(backend, 'testuser', 'testpass')
        token2 = await self._login(backend, 'newuser', 'newpass')
        await self._get_user(backend, token1, 'newuser',
                             failure_key='AuthorizationFailure')
        await self._get_user(backend, token2, 'newuser')
        await self._set_user(backend, token1, 'newuser', 'newpass2',
                             failure_key='AuthorizationFailure')
        await self._set_user(backend, token2, 'newuser', 'newpass2')
        await self._delete_user(backend, token1, 'newuser',
                                failure_key='AuthorizationFailure')
        await self._delete_user(backend, token2, 'newuser')

    async def test_admin_role(self, backend: BackendInterface) -> None:
        token = await self._login(backend, 'testuser', 'testpass')
        await self._set_user(backend, token, 'testuser', 'testpass',
                             params={'role': 'admin'},
                             failure_key='NotAllowedError')
        await self._set_user(backend, self.admin_token, 'testuser', 'testpass',
                             params={'role': 'admin'})
        await self._set_user(backend, token, 'testuser', 'testpass',
                             params={'role': 'admin'})
        await self._set_user(backend, token, 'newuser', 'newpass')
        await self._delete_user(backend, token, 'newuser')

    async def _login(self, backend, authcid: str, secret: str) -> str:
        handlers = SystemHandlers(backend)
        request = LoginRequest(authcid=authcid, secret=secret)
        async with ChannelFor([handlers]) as channel:
            stub = SystemStub(channel)
            response = await stub.Login(request)
        assert SUCCESS == response.result.code
        return response.bearer_token

    async def _get_user(self, backend: BackendInterface,
                        token: str, user: str, *,
                        failure_key: str | None = None) -> None:
        handlers = UserHandlers(backend)
        request = GetUserRequest(user=user)
        metadata = {'auth-token': token}
        async with ChannelFor([handlers]) as channel:
            stub = UserStub(channel)
            response = await stub.GetUser(request, metadata=metadata)
        if failure_key is None:
            assert SUCCESS == response.result.code
            assert user == response.username
        else:
            assert FAILURE == response.result.code
            assert failure_key == response.result.key

    async def _set_user(self, backend: BackendInterface,
                        token: str, user: str, password: str, *,
                        params: Mapping[str, str] | None = None,
                        failure_key: str | None = None) -> None:
        handlers = UserHandlers(backend)
        data = UserData(password=password, params=params)
        request = SetUserRequest(user=user, data=data)
        metadata = {'auth-token': token}
        async with ChannelFor([handlers]) as channel:
            stub = UserStub(channel)
            response = await stub.SetUser(request, metadata=metadata)
        if failure_key is None:
            assert SUCCESS == response.result.code
            assert user == response.username
        else:
            assert FAILURE == response.result.code
            assert failure_key == response.result.key

    async def _delete_user(self, backend: BackendInterface,
                           token: str, user: str, *,
                           failure_key: str | None = None) -> None:
        handlers = UserHandlers(backend)
        request = DeleteUserRequest(user=user)
        metadata = {'auth-token': token}
        async with ChannelFor([handlers]) as channel:
            stub = UserStub(channel)
            response = await stub.DeleteUser(request, metadata=metadata)
        if failure_key is None:
            assert SUCCESS == response.result.code
            assert user == response.username
        else:
            assert FAILURE == response.result.code
            assert failure_key == response.result.key
