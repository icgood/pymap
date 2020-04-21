
from __future__ import annotations

from datetime import datetime, timezone
from typing import AsyncContextManager
from typing_extensions import Final

from grpclib.server import Stream
from pymap.exceptions import ResponseError
from pymap.interfaces.backend import BackendInterface
from pymap.interfaces.session import SessionInterface
from pymap.parsing.message import AppendMessage
from pymap.parsing.specials import Flag, ExtensionOptions
from pymapadmin.grpc.admin_grpc import AdminBase
from pymapadmin.grpc.admin_pb2 import Login, Result, FAILURE, \
    PingRequest, PingResponse, AppendRequest, AppendResponse, \
    UserData, UserResponse, ListUsersRequest, GetUserRequest, \
    SetUserRequest, DeleteUserRequest
from pysasl.external import ExternalResult

from ._util import exit_context
from .. import __version__ as server_version
from ..user import UserMetadata

__all__ = ['AdminHandlers']

_PingStream = Stream[PingRequest, PingResponse]
_AppendStream = Stream[AppendRequest, AppendResponse]
_ListUsersStream = Stream[ListUsersRequest, UserResponse]
_GetUserStream = Stream[GetUserRequest, UserResponse]
_SetUserStream = Stream[SetUserRequest, UserResponse]
_DeleteUserStream = Stream[DeleteUserRequest, UserResponse]


class AdminHandlers(AdminBase):
    """The GRPC handlers, executed when an admin request is received. Each
    handler should receive a request, take action, and send the response.

    See Also:
        :class:`grpclib.server.Server`

    """

    def __init__(self, backend: BackendInterface) -> None:
        super().__init__()
        self.config: Final = backend.config
        self.login: Final = backend.login
        self.users: Final = backend.users

    def _login_as(self, login: Login) -> AsyncContextManager[SessionInterface]:
        creds = ExternalResult(login.user)
        return self.login(creds)

    async def Ping(self, stream: _PingStream) -> None:
        """Respond to a ping request. For example::

            $ pymap-admin ping

        See ``pymap-admin ping --help`` for more options.

        Args:
            stream (:class:`~grpclib.server.Stream`): The stream for the
                request and response.

        """
        request = await stream.recv_message()
        assert request is not None
        resp = PingResponse(server_version=server_version)
        await stream.send_message(resp)

    @exit_context
    async def Append(self, stream: _AppendStream) -> None:
        """Append a message directly to a user's mailbox.

        If the backend session defines a
        :attr:`~pymap.interfaces.session.SessionInterface.filter_set`, the
        active filter implementation will be applied to the appended message,
        such that the message may be discarded, modified, or placed into a
        specific mailbox.

        For example, using the CLI client::

            $ cat message.txt | pymap-admin append user@example.com

        See ``pymap-admin append --help`` for more options.

        Args:
            stream (:class:`~grpclib.server.Stream`): The stream for the
                request and response.

        """
        request = await stream.recv_message()
        assert request is not None
        mailbox = request.mailbox or 'INBOX'
        flag_set = frozenset(Flag(flag) for flag in request.flags)
        when = datetime.fromtimestamp(request.when, timezone.utc)
        append_msg = AppendMessage(request.data, when, flag_set,
                                   ExtensionOptions.empty())
        try:
            async with self._login_as(request.login) as session:
                if session.filter_set is not None:
                    filter_value = await session.filter_set.get_active()
                    if filter_value is not None:
                        compiler = session.filter_set.compiler
                        filter_ = await compiler.compile(filter_value)
                        new_mailbox, append_msg = await filter_.apply(
                            request.sender, request.recipient,
                            mailbox, append_msg)
                        if new_mailbox is None:
                            await stream.send_message(AppendResponse())
                            return
                        else:
                            mailbox = new_mailbox
                append_uid, _ = await session.append_messages(
                    mailbox, [append_msg])
        except ResponseError as exc:
            result = Result(code=FAILURE,
                            response=bytes(exc.get_response(b'.')),
                            key=type(exc).__name__)
            resp = AppendResponse(result=result, mailbox=mailbox)
            await stream.send_message(resp)
        else:
            validity = append_uid.validity
            uid = next(iter(append_uid.uids))
            resp = AppendResponse(mailbox=mailbox, validity=validity, uid=uid)
            await stream.send_message(resp)

    @exit_context
    async def ListUsers(self, stream: _ListUsersStream) -> None:
        """

        See ``pymap-admin get-user --help`` for more options.

        Args:
            stream (:class:`~grpclib.server.Stream`): The stream for the
                request and response.

        """
        if self.users is None:
            raise NotImplementedError()
        request = await stream.recv_message()
        assert request is not None
        match = request.match or None
        async for username in self.users.list_users(match=match):
            resp = UserResponse(username=username)
            await stream.send_message(resp)

    @exit_context
    async def GetUser(self, stream: _GetUserStream) -> None:
        """

        See ``pymap-admin get-user --help`` for more options.

        Args:
            stream (:class:`~grpclib.server.Stream`): The stream for the
                request and response.

        """
        if self.users is None:
            raise NotImplementedError()
        async for request in stream:
            metadata = await self.users.get_user(request.username)
            if metadata is not None:
                user_data = UserData(password=metadata.password,
                                     params=metadata.params)
                resp = UserResponse(username=request.username,
                                    data=user_data)
            else:
                resp = UserResponse(result=Result(code=FAILURE))
            await stream.send_message(resp)

    @exit_context
    async def SetUser(self, stream: _SetUserStream) -> None:
        """

        See ``pymap-admin set-user --help`` for more options.

        Args:
            stream (:class:`~grpclib.server.Stream`): The stream for the
                request and response.

        """
        if self.users is None:
            raise NotImplementedError()
        async for request in stream:
            user_data = request.data
            metadata = UserMetadata(self.config, user_data.password,
                                    params=user_data.params)
            await self.users.set_user(request.username, metadata)
            resp = UserResponse(username=request.username)
            await stream.send_message(resp)

    @exit_context
    async def DeleteUser(self, stream: _DeleteUserStream) -> None:
        """

        See ``pymap-admin delete-user --help`` for more options.

        Args:
            stream (:class:`~grpclib.server.Stream`): The stream for the
                request and response.

        """
        if self.users is None:
            raise NotImplementedError()
        async for request in stream:
            await self.users.delete_user(request.username)
            resp = UserResponse(username=request.username)
            await stream.send_message(resp)
