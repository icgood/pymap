# Copyright (c) 2018 Ian C. Good
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#

from collections import OrderedDict
from copy import copy
from socket import getfqdn
from typing import TYPE_CHECKING, Optional, Callable, Union, Tuple, \
    Awaitable, Any, Dict

from pysasl import SASLAuth  # type: ignore

from .exceptions import CloseConnection
from .interfaces.session import SessionInterface
from .mailbox import MailboxSession
from .parsing.command import CommandAuth, CommandNonAuth, CommandSelect, \
    Command
from .parsing.primitives import ListP, Number, String, Nil
from .parsing.response import ResponseOk, ResponseNo, ResponseBad, Response
from .parsing.response.code import (Capability, PermanentFlags, ReadOnly,
                                    UidNext, UidValidity, Unseen,
                                    ReadWrite)
from .parsing.response.specials import (FlagsResponse, ExistsResponse,
                                        RecentResponse, FetchResponse,
                                        ListResponse, LSubResponse,
                                        SearchResponse, StatusResponse)
from .parsing.specials import FetchAttribute, DateTime
from .parsing.typing import MaybeBytes

__all__ = ['ConnectionState']

if TYPE_CHECKING:
    from .parsing.command.any import *
    from .parsing.command.nonauth import *
    from .parsing.command.auth import *
    from .parsing.command.select import *

    _AuthCommands = Union[AuthenticateCommand, LoginCommand]
    _LoginFunc = Callable[[Any], Awaitable[Optional[SessionInterface]]]
    _CommandFunc = Callable[[Command],
                            Awaitable[Tuple[Response, MailboxSession]]]

fqdn = getfqdn().encode('ascii')


class ConnectionState(object):
    flags_attr = FetchAttribute(b'FLAGS')

    def __init__(self, login: '_LoginFunc') -> None:
        super().__init__()
        self.login = login
        self._session: Optional[SessionInterface] = None
        self._selected: Optional[MailboxSession] = None
        self.auth = SASLAuth([b'PLAIN'])
        self.capability = Capability(
            [b'AUTH=%b' % mech.name for mech in
             self.auth.server_mechanisms])

    @property
    def session(self) -> SessionInterface:
        if self._session is None:
            raise RuntimeError()  # State checking should prevent this.
        return self._session

    @property
    def selected(self) -> MailboxSession:
        if self._selected is None:
            raise RuntimeError()  # State checking should prevent this.
        return self._selected

    async def do_greeting(self):
        return ResponseOk(b'*', b'Server ready ' + fqdn, self.capability)

    async def do_authenticate(self, cmd: '_AuthCommands', creds: Any):
        if not creds:
            return ResponseNo(cmd.tag, b'Invalid authentication mechanism.')
        self._session = await self.login(creds)
        if self._session:
            return ResponseOk(cmd.tag, b'Authentication successful.')
        return ResponseNo(cmd.tag, b'Invalid authentication credentials.')

    async def do_capability(self, cmd: 'CapabilityCommand'):
        response = ResponseOk(cmd.tag, b'Capabilities listed.')
        response.add_untagged(self.capability.to_response())
        return response, None

    async def do_noop(self, cmd: 'NoOpCommand'):
        updates = None
        if self._selected and self._session:
            updates = await self.session.check_mailbox(self.selected)
        return ResponseOk(cmd.tag, b'NOOP completed.'), updates

    async def _select_mailbox(self, cmd: 'SelectCommand', examine: bool):
        self._selected = None
        mailbox, updates = await self.session.select_mailbox(
            cmd.mailbox, examine)
        if updates.readonly:
            resp = ResponseOk(cmd.tag, b'Selected mailbox.', ReadOnly())
            resp.add_untagged_ok(b'Read-only mailbox.', PermanentFlags([]))
        else:
            resp = ResponseOk(cmd.tag, b'Selected mailbox.', ReadWrite())
            resp.add_untagged_ok(b'Flags permitted.',
                                 PermanentFlags(mailbox.permanent_flags))
        resp.add_untagged(FlagsResponse(mailbox.flags))
        resp.add_untagged(ExistsResponse(updates.exists))
        resp.add_untagged(RecentResponse(updates.recent))
        resp.add_untagged_ok(b'Predicted next UID.', UidNext(mailbox.next_uid))
        resp.add_untagged_ok(b'Predicted next UID.',
                             UidValidity(mailbox.uid_validity))
        if mailbox.first_unseen:
            resp.add_untagged_ok(b'First unseen message.',
                                 Unseen(mailbox.first_unseen))
        return resp, updates

    async def do_select(self, cmd: 'SelectCommand'):
        return await self._select_mailbox(cmd, False)

    async def do_examine(self, cmd: 'ExamineCommand'):
        return await self._select_mailbox(cmd, True)

    async def do_create(self, cmd: 'CreateCommand'):
        if cmd.mailbox == 'INBOX':
            return ResponseNo(cmd.tag, b'Cannot create INBOX.'), None
        updates = await self.session.create_mailbox(
            cmd.mailbox, selected=self._selected)
        return ResponseOk(cmd.tag, b'Mailbox created successfully.'), updates

    async def do_delete(self, cmd: 'DeleteCommand'):
        if cmd.mailbox == 'INBOX':
            return ResponseNo(cmd.tag, b'Cannot delete INBOX.')
        updates = await self.session.delete_mailbox(
            cmd.mailbox, selected=self._selected)
        return ResponseOk(cmd.tag, b'Mailbox deleted successfully.'), updates

    async def do_rename(self, cmd: 'RenameCommand'):
        if cmd.to_mailbox == 'INBOX':
            return ResponseNo(cmd.tag, b'Cannot rename to INBOX.')
        updates = await self.session.rename_mailbox(
            cmd.from_mailbox, cmd.to_mailbox, selected=self._selected)
        return ResponseOk(cmd.tag, b'Mailbox renamed successfully.'), updates

    async def do_status(self, cmd: 'StatusCommand'):
        mailbox, updates = await self.session.get_mailbox(
            cmd.mailbox, selected=self._selected)
        data = OrderedDict()  # type: ignore
        for attr in cmd.status_list:
            if attr == b'MESSAGES':
                data[attr] = Number(mailbox.exists)
            elif attr == b'RECENT':
                data[attr] = Number(mailbox.recent)
            elif attr == b'UNSEEN':
                data[attr] = Number(mailbox.unseen)
            elif attr == b'UIDNEXT':
                data[attr] = Number(mailbox.next_uid)
            elif attr == b'UIDVALIDITY':
                data[attr] = Number(mailbox.uid_validity)
        resp = ResponseOk(cmd.tag, b'STATUS completed.')
        resp.add_untagged(StatusResponse(cmd.mailbox, data))
        return resp, updates

    async def do_append(self, cmd: 'AppendCommand'):
        updates = await self.session.append_message(
            cmd.mailbox, cmd.message, cmd.flag_set, cmd.when,
            selected=self._selected)
        return ResponseOk(cmd.tag, b'APPEND completed.'), updates

    async def do_subscribe(self, cmd: 'SubscribeCommand'):
        updates = await self.session.subscribe(
            cmd.mailbox, selected=self._selected)
        return ResponseOk(cmd.tag, b'SUBSCRIBE completed.'), updates

    async def do_unsubscribe(self, cmd: 'UnsubscribeCommand'):
        updates = await self.session.unsubscribe(
            cmd.mailbox, selected=self._selected)
        return ResponseOk(cmd.tag, b'UNSUBSCRIBE completed.'), updates

    async def do_list(self, cmd: 'ListCommand'):
        mailboxes, updates = await self.session.list_mailboxes(
            cmd.ref_name, cmd.filter, selected=self._selected)
        resp = ResponseOk(cmd.tag, b'LIST completed.')
        for name, sep, attrs in mailboxes:
            resp.add_untagged(ListResponse(name, sep, **attrs))
        return resp, updates

    async def do_lsub(self, cmd: 'LSubCommand'):
        mailboxes, updates = await self.session.list_mailboxes(
            cmd.ref_name, cmd.filter, subscribed=True, selected=self._selected)
        resp = ResponseOk(cmd.tag, b'LSUB completed.')
        for name, sep, attrs in mailboxes:
            resp.add_untagged(LSubResponse(name, sep, **attrs))
        return resp, updates

    async def do_check(self, cmd: 'CheckCommand'):
        updates = await self.session.check_mailbox(
            self.selected, housekeeping=True)
        return ResponseOk(cmd.tag, b'CHECK completed.'), updates

    async def do_close(self, cmd: 'CloseCommand'):
        await self.session.expunge_mailbox(self.selected)
        self._selected = None
        return ResponseOk(cmd.tag, b'CLOSE completed.'), None

    async def do_expunge(self, cmd: 'ExpungeCommand'):
        updates = await self.session.expunge_mailbox(self.selected)
        resp = ResponseOk(cmd.tag, b'EXPUNGE completed.')
        return resp, updates

    async def do_copy(self, cmd: 'CopyCommand'):
        updates = await self.session.copy_messages(
            self.selected, cmd.sequence_set, cmd.mailbox)
        return ResponseOk(cmd.tag, b'COPY completed.'), updates

    async def do_fetch(self, cmd: 'FetchCommand'):
        messages, updates = await self.session.fetch_messages(
            self.selected, cmd.sequence_set, frozenset(cmd.attributes))
        resp = ResponseOk(cmd.tag, b'FETCH completed.')
        for msg_seq, msg in messages:
            fetch_data = OrderedDict()  # type: ignore
            for attr in cmd.attributes:
                if attr.value == b'UID':
                    fetch_data[attr] = Number(msg.uid)
                elif attr.value == b'FLAGS':
                    flags = msg.get_flags(self.selected)
                    fetch_data[attr] = ListP(flags, sort=True)
                elif attr.value == b'INTERNALDATE':
                    if msg.internal_date:
                        fetch_data[attr] = DateTime(msg.internal_date)
                    else:
                        fetch_data[attr] = Nil()
                elif attr.value == b'ENVELOPE':
                    fetch_data[attr] = msg.get_envelope_structure()
                elif attr.value == b'BODYSTRUCTURE':
                    fetch_data[attr] = msg.get_body_structure().extended
                elif attr.value in (b'BODY', b'BODY.PEEK'):
                    if not attr.section:
                        fetch_data[attr] = msg.get_body_structure()
                    elif not attr.section.msgtext:
                        fetch_data[attr] = String.build(msg.get_body(
                            attr.section.parts))
                    elif attr.section.msgtext == b'TEXT':
                        fetch_data[attr] = String.build(msg.get_text(
                            attr.section.parts))
                    elif attr.section.msgtext in (b'HEADER', b'MIME'):
                        fetch_data[attr] = String.build(msg.get_headers(
                            attr.section.parts))
                    elif attr.section.msgtext == b'HEADER.FIELDS':
                        fetch_data[attr] = String.build(msg.get_headers(
                            attr.section.parts, attr.section.headers))
                    elif attr.section.msgtext == b'HEADER.FIELDS.NOT':
                        fetch_data[attr] = String.build(msg.get_headers(
                            attr.section.parts, attr.section.headers, True))
                elif attr.value == b'RFC822':
                    fetch_data[attr] = String.build(msg.get_body())
                elif attr.value == b'RFC822.HEADER':
                    fetch_data[attr] = String.build(msg.get_headers())
                elif attr.value == b'RFC822.TEXT':
                    fetch_data[attr] = String.build(msg.get_text())
                elif attr.value == b'RFC822.SIZE':
                    fetch_data[attr] = Number(msg.get_size())
            resp.add_untagged(FetchResponse(msg_seq, fetch_data))
        return resp, updates

    async def do_search(self, cmd: 'SearchCommand'):
        messages, updates = await self.session.search_mailbox(
            self.selected, cmd.keys)
        resp = ResponseOk(cmd.tag, b'SEARCH completed.')
        if cmd.uid:
            msg_ids = [msg.uid for _, msg in messages]
        else:
            msg_ids = [msg_seq for msg_seq, _ in messages]
        resp.add_untagged(SearchResponse(msg_ids))
        return resp, updates

    async def do_store(self, cmd: 'StoreCommand'):
        messages, updates = await self.session.update_flags(
            self.selected, cmd.sequence_set, cmd.flag_set, cmd.mode)
        resp = ResponseOk(cmd.tag, b'STORE completed.')
        if not cmd.silent:
            for msg_seq, msg in messages:
                fetch_data: Dict[FetchAttribute, MaybeBytes] = OrderedDict()
                fetch_data[FetchAttribute(b'FLAGS')] = ListP(
                    msg.get_flags(self.selected), sort=True)
                if cmd.uid:
                    fetch_data[FetchAttribute(b'UID')] = Number(msg.uid)
                resp.add_untagged(FetchResponse(msg_seq, fetch_data))
        return resp, updates

    @classmethod
    async def do_logout(cls, cmd: 'LogoutCommand'):
        raise CloseConnection()

    async def do_command(self, cmd: Command):
        if self._session and isinstance(cmd, CommandNonAuth):
            msg = cmd.command + b': Already authenticated.'
            return ResponseBad(cmd.tag, msg)
        elif not self._session and isinstance(cmd, CommandAuth):
            msg = cmd.command + b': Must authenticate first.'
            return ResponseBad(cmd.tag, msg)
        elif not self._selected and isinstance(cmd, CommandSelect):
            msg = cmd.command + b': Must select a mailbox first.'
            return ResponseBad(cmd.tag, msg)
        func_name = 'do_' + str(cmd.command, 'ascii').lower()
        try:
            func: '_CommandFunc' = getattr(self, func_name)
        except AttributeError:
            return ResponseNo(cmd.tag, cmd.command + b': Not Implemented')
        response, selected = await func(cmd)
        if selected:
            for update in selected.drain_updates():
                response.add_untagged(update)
        self._selected = copy(selected)
        return response
