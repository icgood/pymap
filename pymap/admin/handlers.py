
from datetime import datetime, timezone
from typing_extensions import Final

from pymap.exceptions import ResponseError
from pymap.interfaces.backend import BackendInterface
from pymap.interfaces.message import AppendMessage
from pymap.interfaces.session import SessionInterface
from pymap.parsing.specials import Flag, ExtensionOptions
from pysasl.external import ExternalResult

from .grpc.admin_grpc import AdminBase

__all__ = ['AdminHandlers']


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

    async def _login_as(self, user: str) -> SessionInterface:
        creds = ExternalResult(user)
        return await self.login(creds, self.config)

    @property
    def _with_filter(self) -> bool:
        return not self.config.args.no_filter

    async def Append(self, stream) -> None:
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
        from .grpc.admin_pb2 import AppendRequest, AppendResponse, \
            ERROR_RESPONSE
        request: AppendRequest = await stream.recv_message()
        mailbox = request.mailbox or 'INBOX'
        flag_set = frozenset(Flag(flag) for flag in request.flags)
        when = datetime.fromtimestamp(request.when, timezone.utc)
        append_msg = AppendMessage(request.data, flag_set, when,
                                   ExtensionOptions.empty())
        try:
            session = await self._login_as(request.user)
            if self._with_filter and session.filter_set is not None:
                filter_value = await session.filter_set.get_active()
                if filter_value is not None:
                    compiler = session.filter_set.compiler
                    filter_ = await compiler.compile(filter_value)
                    new_mailbox, append_msg = await filter_.apply(
                        request.sender, request.recipient, mailbox, append_msg)
                    if new_mailbox is None:
                        await stream.send_message(AppendResponse())
                        return
                    else:
                        mailbox = new_mailbox
            append_uid, _ = await session.append_messages(
                mailbox, [append_msg])
        except ResponseError as exc:
            resp = AppendResponse(result=ERROR_RESPONSE,
                                  error_type=type(exc).__name__,
                                  error_response=bytes(exc.get_response(b'.')),
                                  mailbox=mailbox)
            await stream.send_message(resp)
        else:
            validity = append_uid.validity
            uid = next(iter(append_uid.uids))
            resp = AppendResponse(mailbox=mailbox, validity=validity, uid=uid)
            await stream.send_message(resp)
