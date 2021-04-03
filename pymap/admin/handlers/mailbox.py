
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from grpclib.server import Stream
from pymap.parsing.message import AppendMessage
from pymap.parsing.specials import Flag, ExtensionOptions
from pymapadmin.grpc.admin_grpc import MailboxBase
from pymapadmin.grpc.admin_pb2 import AppendRequest, AppendResponse

from . import BaseHandler

__all__ = ['MailboxHandlers']

_AppendStream = Stream[AppendRequest, AppendResponse]


class MailboxHandlers(MailboxBase, BaseHandler):
    """The GRPC handlers, executed when an admin request is received. Each
    handler should receive a request, take action, and send the response.

    See Also:
        :class:`grpclib.server.Server`

    """

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
        sender = request.sender if request.HasField('sender') else ''
        recipient = request.recipient \
            if request.HasField('recipient') else request.user
        mailbox = request.mailbox if request.HasField('mailbox') else 'INBOX'
        flag_set = frozenset(Flag(flag) for flag in request.flags)
        when = datetime.fromtimestamp(request.when, timezone.utc)
        append_msg = AppendMessage(request.data, when, flag_set,
                                   ExtensionOptions.empty())
        validity: Optional[int] = None
        uid: Optional[int] = None
        async with self.catch_errors('Append') as result, \
                self.login_as(stream.metadata, request.user) as identity, \
                self.with_session(identity) as session:
            if session.filter_set is not None:
                filter_value = await session.filter_set.get_active()
                if filter_value is not None:
                    compiler = session.filter_set.compiler
                    filter_ = await compiler.compile(filter_value)
                    new_mailbox, append_msg = await filter_.apply(
                        sender, recipient, mailbox, append_msg)
                    if new_mailbox is None:
                        await stream.send_message(AppendResponse())
                        return
                    else:
                        mailbox = new_mailbox
            append_uid, _ = await session.append_messages(
                mailbox, [append_msg])
            validity = append_uid.validity
            uid = next(iter(append_uid.uids))
        resp = AppendResponse(result=result, mailbox=mailbox,
                              validity=validity, uid=uid)
        await stream.send_message(resp)
