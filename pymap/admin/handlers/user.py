
from __future__ import annotations

from typing import TypeAlias

from grpclib.server import Stream
from pymap.frozen import frozendict
from pymap.user import Passwords, UserMetadata
from pymapadmin.grpc.admin_grpc import UserBase
from pymapadmin.grpc.admin_pb2 import \
    UserData, UserResponse, GetUserRequest, SetUserRequest, DeleteUserRequest

from . import BaseHandler

__all__ = ['UserHandlers']

_GetUserStream: TypeAlias = Stream[GetUserRequest, UserResponse]
_SetUserStream: TypeAlias = Stream[SetUserRequest, UserResponse]
_DeleteUserStream: TypeAlias = Stream[DeleteUserRequest, UserResponse]


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
        user: str | None = None
        user_data: UserData | None = None
        entity_tag: int | None = None
        async with (self.catch_errors('GetUser') as result,
                    self.login_as(stream.metadata, request.user) as identity):
            user = identity.name
            metadata = await identity.get()
            entity_tag = metadata.entity_tag
            user_data = UserData(params=metadata.params, roles=metadata.roles)
            if metadata.password is not None:
                user_data.password = metadata.password
        resp = UserResponse(result=result, user=user, entity_tag=entity_tag,
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
        user: str | None = None
        entity_tag: int | None = None
        async with (self.catch_errors('SetUser') as result,
                    self.login_as(stream.metadata, request.user) as identity):
            user = identity.name
            user_data = request.data
            password = await Passwords(self.config).hash_password(
                user_data.password if user_data.HasField('password') else None)
            roles: frozenset[str] = frozenset(user_data.roles)
            params: frozendict[str, str] = frozendict(user_data.params)
            previous_entity_tag: int | None = None
            if request.HasField('previous_entity_tag'):
                previous_entity_tag = request.previous_entity_tag
            elif request.overwrite:
                previous_entity_tag = UserMetadata.REPLACE_ANY
            metadata = UserMetadata(
                self.config, request.user,
                previous_entity_tag=previous_entity_tag,
                password=password, roles=roles, params=params)
            entity_tag = await identity.set(metadata)
        resp = UserResponse(result=result, user=user, entity_tag=entity_tag)
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
        async with (self.catch_errors('DeleteUser') as result,
                    self.login_as(stream.metadata, request.user) as identity):
            await identity.delete()
        resp = UserResponse(result=result, user=request.user)
        await stream.send_message(resp)
