# Copyright (c) 2014 Ian C. Good
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

from copy import copy
from socket import getfqdn
from typing import Optional, Callable

from pysasl import SASLAuth

from .core import PymapError
from .exceptions import (MailboxNotFound, MailboxConflict, MailboxHasChildren,
                         MailboxReadOnly, AppendFailure)
from .interfaces import MailboxState, SessionInterface
from .parsing.command import CommandAuth, CommandNonAuth, CommandSelect
from .parsing.primitives import List, Number
from .parsing.response import (ResponseOk, ResponseNo, ResponseBad,
                               ResponseBye)
from .parsing.response.code import (Capability, PermanentFlags, ReadOnly,
                                    UidNext, UidValidity, Unseen,
                                    TryCreate, ReadWrite)
from .parsing.response.specials import (FlagsResponse, ExistsResponse,
                                        RecentResponse, FetchResponse,
                                        ListResponse, LSubResponse,
                                        SearchResponse, StatusResponse)
from .parsing.specials import FetchAttribute, DateTime

__all__ = ['CloseConnection', 'ConnectionState']

fqdn = getfqdn().encode('ascii')


class CloseConnection(PymapError):
    """Raised when the connection should be closed immediately after sending
    the provided response.

    :param response: The response to send before closing the connection.
    :type response: pymap.parsing.response.Response

    """

    def __init__(self, response):
        super().__init__()
        self.response = response


class ConnectionState(object):
    flags_attr = FetchAttribute(b'FLAGS')

    def __init__(self, login):
        super().__init__()
        self.login = login  # type: Callable[..., Optional[SessionInterface]]
        self.session = None  # type: Optional[SessionInterface]
        self.selected = None  # type: Optional[MailboxState]
        self.capability = Capability(
            [b'AUTH=%b' % mech.name for mech in
             SASLAuth([b'PLAIN']).server_mechanisms])

    async def do_greeting(self):
        return ResponseOk(b'*', b'Server ready ' + fqdn, self.capability)

    async def do_authenticate(self, cmd, result):
        if not result:
            return ResponseNo(cmd.tag, b'Invalid authentication mechanism.')
        self.session = await self.login(result)
        if self.session:
            return ResponseOk(cmd.tag, b'Authentication successful.')
        return ResponseNo(cmd.tag, b'Invalid authentication credentials.')

    async def do_capability(self, cmd):
        response = ResponseOk(cmd.tag, b'Capabilities listed.')
        response.add_untagged(self.capability.to_response())
        return response, None

    async def do_noop(self, cmd):
        updates = None
        if self.selected:
            updates = await self.session.check_mailbox(self.selected)
        return ResponseOk(cmd.tag, b'NOOP completed.'), updates

    async def _select_mailbox(self, cmd, examine):
        try:
            mailbox, updates = await self.session.get_mailbox(cmd.mailbox)
        except MailboxNotFound:
            return ResponseNo(cmd.tag, b'Mailbox does not exist.'), None
        self.selected = mailbox
        self.updates = copy(updates)
        if mailbox.readonly or examine:
            resp = ResponseOk(cmd.tag, b'Selected mailbox.', ReadOnly())
            resp.add_untagged_ok(b'Read-only mailbox.', PermanentFlags([]))
        else:
            resp = ResponseOk(cmd.tag, b'Selected mailbox.', ReadWrite())
            resp.add_untagged_ok(b'Flags permitted.',
                                 PermanentFlags(mailbox.permanent_flags))
        resp.add_untagged(FlagsResponse(mailbox.flags))
        resp.add_untagged(ExistsResponse(mailbox.exists))
        resp.add_untagged(RecentResponse(mailbox.recent))
        resp.add_untagged_ok(b'Predicted next UID.', UidNext(mailbox.next_uid))
        resp.add_untagged_ok(b'Predicted next UID.',
                             UidValidity(mailbox.uid_validity))
        if mailbox.first_unseen:
            resp.add_untagged_ok(b'First unseen message.',
                                 Unseen(mailbox.first_unseen))
        return resp, updates

    async def do_select(self, cmd):
        return await self._select_mailbox(cmd, False)

    async def do_examine(self, cmd):
        return await self._select_mailbox(cmd, True)

    async def do_create(self, cmd):
        if cmd.mailbox == 'INBOX':
            return ResponseNo(cmd.tag, b'Cannot create INBOX.'), None
        try:
            updates = await self.session.create_mailbox(
                cmd.mailbox, selected=self.selected)
        except MailboxConflict:
            return ResponseNo(cmd.tag, b'Mailbox already exists.')
        return ResponseOk(cmd.tag, b'Mailbox created successfully.'), updates

    async def do_delete(self, cmd):
        if cmd.mailbox == 'INBOX':
            return ResponseNo(cmd.tag, b'Cannot delete INBOX.')
        try:
            updates = await self.session.delete_mailbox(
                cmd.mailbox, selected=self.selected)
        except MailboxNotFound:
            return ResponseNo(cmd.tag, b'Mailbox not found.'), None
        except MailboxHasChildren:
            msg = b'Mailbox has inferior hierarchical names.'
            return ResponseNo(cmd.tag, msg), None
        return ResponseOk(cmd.tag, b'Mailbox deleted successfully.'), updates

    async def do_rename(self, cmd):
        if cmd.to_mailbox == 'INBOX':
            return ResponseNo(cmd.tag, b'Cannot rename to INBOX.')
        try:
            updates = await self.session.rename_mailbox(
                cmd.from_mailbox, cmd.to_mailbox, selected=self.selected)
        except MailboxNotFound:
            return ResponseNo(cmd.tag, b'Mailbox not found.'), None
        except MailboxConflict:
            return ResponseNo(cmd.tag, b'Mailbox already exists.'), None
        return ResponseOk(cmd.tag, b'Mailbox renamed successfully.'), updates

    async def do_status(self, cmd):
        try:
            mailbox, updates = await self.session.get_mailbox(
                cmd.mailbox, selected=self.selected)
        except MailboxNotFound:
            return ResponseNo(cmd.tag, b'Mailbox does not exist.'), None
        data = {}
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

    async def do_append(self, cmd):
        try:
            updates = await self.session.append_message(
                cmd.mailbox, cmd.message, cmd.flag_set, cmd.when,
                selected=self.selected)
        except MailboxNotFound:
            return ResponseNo(cmd.tag, b'Mailbox does not exist.',
                              TryCreate()), None
        except AppendFailure as exc:
            return ResponseNo(cmd.tag, bytes(str(exc), 'utf-8')), None
        return ResponseOk(cmd.tag, b'APPEND completed.'), updates

    async def do_subscribe(self, cmd):
        updates = await self.session.subscribe(
            cmd.mailbox, selected=self.selected)
        return ResponseOk(cmd.tag, b'SUBSCRIBE completed.'), updates

    async def do_unsubscribe(self, cmd):
        updates = await self.session.unsubscribe(
            cmd.mailbox, selected=self.selected)
        return ResponseOk(cmd.tag, b'UNSUBSCRIBE completed.'), updates

    async def do_list(self, cmd):
        mailboxes, updates = await self.session.list_mailboxes(
            cmd.ref_name, cmd.filter, selected=self.selected)
        resp = ResponseOk(cmd.tag, b'LIST completed.')
        for name, sep, attrs in mailboxes:
            resp.add_untagged(ListResponse(name, sep, **attrs))
        return resp, updates

    async def do_lsub(self, cmd):
        mailboxes, updates = await self.session.list_mailboxes(
            cmd.ref_name, cmd.filter, subscribed=True, selected=self.selected)
        resp = ResponseOk(cmd.tag, b'LSUB completed.')
        for name, sep, attrs in mailboxes:
            resp.add_untagged(LSubResponse(name, sep, **attrs))
        return resp, updates

    async def do_check(self, cmd):
        updates = await self.session.check_mailbox(
            self.selected, housekeeping=True)
        return ResponseOk(cmd.tag, b'CHECK completed.'), updates

    async def do_close(self, cmd):
        try:
            await self.session.expunge_mailbox(self.selected)
        except MailboxReadOnly:
            pass
        self.selected = None
        return ResponseOk(cmd.tag, b'CLOSE completed.'), None

    async def do_expunge(self, cmd):
        try:
            updates = await self.session.expunge_mailbox(self.selected)
        except MailboxReadOnly:
            return ResponseNo(cmd.tag, b'Mailbox is read-only.',
                              ReadOnly()), None
        resp = ResponseOk(cmd.tag, b'EXPUNGE completed.')
        return resp, updates

    async def do_copy(self, cmd):
        try:
            updates = await self.session.copy_messages(
                self.selected, cmd.sequence_set, cmd.mailbox)
        except MailboxNotFound:
            return ResponseNo(cmd.tag, b'Mailbox does not exist.',
                              TryCreate()), None
        return ResponseOk(cmd.tag, b'COPY completed.'), updates

    async def do_fetch(self, cmd):
        messages, updates = await self.session.fetch_messages(
            self.selected, cmd.sequence_set, cmd.attributes)
        resp = ResponseOk(cmd.tag, b'FETCH completed.')
        for msg_seq, msg in messages:
            fetch_data = {}
            for attr in cmd.attributes:
                if attr.attribute == b'UID':
                    fetch_data[attr] = Number(msg.uid)
                elif attr.attribute == b'FLAGS':
                    fetch_data[attr] = List(msg.get_flags(self.selected))
                elif attr.attribute == b'INTERNALDATE':
                    fetch_data[attr] = DateTime(msg.internal_date)
                elif attr.attribute == b'ENVELOPE':
                    fetch_data[attr] = msg.get_envelope_structure()
                elif attr.attribute == b'BODYSTRUCTURE':
                    fetch_data[attr] = msg.get_body_structure()
                elif attr.attribute in (b'BODY', b'BODY.PEEK'):
                    if not attr.section:
                        fetch_data[attr] = msg.get_body_structure()
                    elif not attr.section[1]:
                        fetch_data[attr] = msg.get_body(attr.section[0])
                    elif attr.section[1] == b'TEXT':
                        fetch_data[attr] = msg.get_text(attr.section[0])
                    elif attr.section[1] in (b'HEADER', b'MIME'):
                        fetch_data[attr] = msg.get_headers(attr.section[0])
                    elif attr.section[1] == b'HEADER.FIELDS':
                        fetch_data[attr] = msg.get_headers(
                            attr.section[0], attr.section[2])
                    elif attr.section[1] == b'HEADER.FIELDS.NOT':
                        fetch_data[attr] = msg.get_headers(
                            attr.section[0], attr.section[2], True)
                elif attr.attribute == b'RFC822':
                    fetch_data[attr] = msg.get_body()
                elif attr.attribute == b'RFC822.HEADER':
                    fetch_data[attr] = msg.get_headers()
                elif attr.attribute == b'RFC822.TEXT':
                    fetch_data[attr] = msg.get_text()
                elif attr.attribute == b'RFC822.SIZE':
                    fetch_data[attr] = msg.get_size()
            resp.add_untagged(FetchResponse(msg_seq, fetch_data))
        return resp, updates

    async def do_search(self, cmd):
        seqs, updates = await self.session.search_mailbox(
            self.selected, cmd.keys)
        resp = ResponseOk(cmd.tag, b'SEARCH completed.')
        resp.add_untagged(SearchResponse(seqs))
        return resp, updates

    async def do_store(self, cmd):
        updates = await self.session.update_flags(
            self.selected, cmd.sequence_set, cmd.flag_set, cmd.mode,
            silent=cmd.silent)
        resp = ResponseOk(cmd.tag, b'STORE completed.')
        return resp, updates

    @classmethod
    async def do_logout(cls, cmd):
        response = ResponseOk(cmd.tag, b'Logout successful.')
        response.add_untagged(ResponseBye(b'Logging out.'))
        raise CloseConnection(response)

    async def do_command(self, cmd):
        if self.session and isinstance(cmd, CommandNonAuth):
            msg = cmd.command + b': Already authenticated.'
            return ResponseBad(cmd.tag, msg)
        elif not self.session and isinstance(cmd, CommandAuth):
            msg = cmd.command + b': Must authenticate first.'
            return ResponseBad(cmd.tag, msg)
        elif not self.selected and isinstance(cmd, CommandSelect):
            msg = cmd.command + b': Must select a mailbox first.'
            return ResponseBad(cmd.tag, msg)
        func_name = 'do_' + str(cmd.command, 'ascii').lower()
        try:
            func = getattr(self, func_name)
        except AttributeError:
            return ResponseNo(cmd.tag, cmd.command + b': Not Implemented')
        response, updated = await func(cmd)
        if updated and self.selected:
            for update in updated.get_responses(self.selected):
                response.add_untagged(update)
            self.selected = updated
        return response
