
from __future__ import annotations

from typing import Optional

from grpclib.server import Stream
from pymap.user import UserMetadata
from pymapadmin.grpc.admin_grpc import UserBase
from pymapadmin.grpc.admin_pb2 import \
    UserData, UserResponse, GetUserRequest, SetUserRequest, DeleteUserRequest

from . import BaseHandler

__all__ = ['UserHandlers']

_GetUserStream = Stream[GetUserRequest, UserResponse]
_SetUserStream = Stream[SetUserRequest, UserResponse]
_DeleteUserStream = Stream[DeleteUserRequest, UserResponse]


class UserHandlers(UserBase, BaseHandler):
    """The GRPC handlers, executed when an admin request is received. Each
    handler should receive a request, take action, and send the response.

    See Also:
        :class:`grpclib.server.Server`

    """

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
                self.login_as(stream.metadata, request.user) as identity:
            username = identity.name
            metadata = await identity.get()
            user_data = UserData(params=metadata.params)
            if metadata.password is not None:
                user_data.password = metadata.password
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
                self.login_as(stream.metadata, request.user) as identity:
            user_data = request.data
            password = self.config.hash_context.hash(user_data.password) \
                if user_data.HasField('password') else None
            metadata = UserMetadata(self.config, password=password,
                                    **user_data.params)
            await identity.set(metadata)
        resp = UserResponse(result=result, username=request.user)
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
                self.login_as(stream.metadata, request.user) as identity:
            await identity.delete()
        resp = UserResponse(result=result, username=request.user)
        await stream.send_message(resp)
