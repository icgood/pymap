
from datetime import datetime, timezone
from typing_extensions import Final

from pymap.exceptions import InvalidAuth, MailboxNotFound
from pymap.interfaces.backend import BackendInterface
from pymap.interfaces.message import AppendMessage
from pymap.interfaces.session import SessionInterface
from pymap.parsing.specials import Flag, ExtensionOptions
from pysasl.external import ExternalResult

from .grpc.admin_grpc import AdminBase

__all__ = ['GrpcHandlers']


class GrpcHandlers(AdminBase):
    """The GRPC handlers, executed when an admin request is received. Each
    handler should receive a request, take action, and send the response.

    """

    def __init__(self, backend: BackendInterface) -> None:
        super().__init__()
        self.config: Final = backend.config
        self.login: Final = backend.login

    async def _login_as(self, user: str) -> SessionInterface:
        creds = ExternalResult(user)
        return await self.login(creds, self.config)

    async def Append(self, stream) -> None:
        """Append a message directly to a user's mailbox. For example::

            $ cat message.txt | pymap-admin append user@example.com

        See ``pymap-admin append --help`` for more options.

        Args:
            stream: The stream for the request and response.

        """
        from .grpc.admin_pb2 import AppendRequest, AppendResponse, \
            USER_NOT_FOUND, MAILBOX_NOT_FOUND
        request: AppendRequest = await stream.recv_message()
        flag_set = frozenset(Flag(flag) for flag in request.flags)
        when = datetime.fromtimestamp(request.when, timezone.utc)
        append_msg = AppendMessage(request.data, flag_set, when,
                                   ExtensionOptions.empty())
        try:
            session = await self._login_as(request.user)
            append_uid, _ = await session.append_messages(
                request.mailbox, [append_msg])
        except InvalidAuth:
            resp = AppendResponse(result=USER_NOT_FOUND)
        except MailboxNotFound:
            resp = AppendResponse(result=MAILBOX_NOT_FOUND)
        else:
            validity = append_uid.validity
            uid = next(iter(append_uid.uids))
            resp = AppendResponse(validity=validity, uid=uid)
        await stream.send_message(resp)
