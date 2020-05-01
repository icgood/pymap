
from __future__ import annotations

from typing import Optional

from grpclib.server import Stream
from pymap.exceptions import NotSupportedError
from pymap.user import UserMetadata
from pymapadmin.grpc.admin_grpc import UserBase
from pymapadmin.grpc.admin_pb2 import \
    ListUsersRequest, ListUsersResponse, UserData, UserResponse, \
    GetUserRequest, SetUserRequest, DeleteUserRequest

from . import LoginHandler

__all__ = ['UserHandlers']

_ListUsersStream = Stream[ListUsersRequest, ListUsersResponse]
_GetUserStream = Stream[GetUserRequest, UserResponse]
_SetUserStream = Stream[SetUserRequest, UserResponse]
_DeleteUserStream = Stream[DeleteUserRequest, UserResponse]


class UserHandlers(UserBase, LoginHandler):
    """The GRPC handlers, executed when an admin request is received. Each
    handler should receive a request, take action, and send the response.

    See Also:
        :class:`grpclib.server.Server`

    """

    async def ListUsers(self, stream: _ListUsersStream) -> None:
        """

        See ``pymap-admin get-user --help`` for more options.

        Args:
            stream (:class:`~grpclib.server.Stream`): The stream for the
                request and response.

        """
        request = await stream.recv_message()
        assert request is not None
        async with self.catch_errors('ListUsers') as result, \
                self.login_as(request.login) as session:
            if session.users is None:
                raise NotSupportedError()
            match = request.match or None
            async for users in session.users.list_users(match=match):
                resp = ListUsersResponse(users=users)
                await stream.send_message(resp)
        resp = ListUsersResponse(result=result)
        await stream.send_message(resp)

    async def GetUser(self, stream: _GetUserStream) -> None:
        """

        See ``pymap-admin get-user --help`` for more options.

        Args:
            stream (:class:`~grpclib.server.Stream`): The stream for the
                request and response.

        """
        request = await stream.recv_message()
        assert request is not None
        username: Optional[str] = None
        user_data: Optional[UserData] = None
        async with self.catch_errors('GetUser') as result, \
                self.login_as(request.login) as session:
            if session.users is None:
                raise NotSupportedError()
            username = session.owner
            metadata = await session.users.get_user(username)
            user_data = UserData(password=metadata.password,
                                 params=metadata.params)
        resp = UserResponse(result=result, username=username,
                            data=user_data)
        await stream.send_message(resp)

    async def SetUser(self, stream: _SetUserStream) -> None:
        """

        See ``pymap-admin set-user --help`` for more options.

        Args:
            stream (:class:`~grpclib.server.Stream`): The stream for the
                request and response.

        """
        request = await stream.recv_message()
        assert request is not None
        async with self.catch_errors('SetUser') as result, \
                self.login_as(request.login) as session:
            if session.users is None:
                raise NotSupportedError()
            user_data = request.data
            password = self.config.hash_context.hash(user_data.password)
            metadata = UserMetadata(self.config, password,
                                    params=user_data.params)
            await session.users.set_user(session.owner, metadata)
        resp = UserResponse(result=result)
        await stream.send_message(resp)

    async def DeleteUser(self, stream: _DeleteUserStream) -> None:
        """

        See ``pymap-admin delete-user --help`` for more options.

        Args:
            stream (:class:`~grpclib.server.Stream`): The stream for the
                request and response.

        """
        request = await stream.recv_message()
        assert request is not None
        async with self.catch_errors('DeleteUser') as result, \
                self.login_as(request.login) as session:
            if session.users is None:
                raise NotSupportedError()
            await session.users.delete_user(session.owner)
        resp = UserResponse(result=result)
        await stream.send_message(resp)
