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

from socket import getfqdn

from pysasl import SASLAuth

from .core import PymapError
from .exceptions import (MailboxNotFound, MailboxConflict, MailboxHasChildren,
                         MailboxReadOnly, AppendFailure)
from .parsing.command import CommandAuth, CommandNonAuth, CommandSelect
from .parsing.primitives import List, Number
from .parsing.response import (Response, ResponseOk, ResponseNo, ResponseBad,
                               ResponseBye)
from .parsing.response.code import (Capability, PermanentFlags, ReadOnly,
                                    ReadWrite, UidNext, UidValidity, Unseen,
                                    TryCreate)
from .parsing.response.specials import (FlagsResponse, ExistsResponse,
                                        RecentResponse, ExpungeResponse,
                                        FetchResponse, ListResponse,
                                        LSubResponse, SearchResponse)
from .parsing.specials import FetchAttribute, DateTime

__all__ = ['CloseConnection', 'MailboxState', 'ConnectionState']

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


class MailboxState(object):
    """Used to track relevant information about a mailbox to correctly
    report updates made by other clients.

    """

    def __init__(self, name):
        self.name = name

        #: Tracks the sequence IDs that have been expunged by other clients
        #: since last reported.
        self.expunge = set()

        #: Tracks the number of messages that exist in the mailbox.
        self.exists = 0

        #: Tracks the number of recent messages in the mailbox.
        self.recent = 0


class ConnectionState(object):
    flags_attr = FetchAttribute(b'FLAGS')

    def __init__(self, transport, login):
        super().__init__()
        self.transport = transport
        self.login = login
        self.auth = SASLAuth([b'PLAIN'])
        self.session = None
        self.selected = None
        self.expunge_buffer = set()
        self.before_exists = 0
        self.before_recent = 0
        self.capability = Capability(
            [b'AUTH=%b' % mech.name for mech in self.auth.server_mechanisms])

    async def do_greeting(self):
        return ResponseOk(b'*', b'Server ready ' + fqdn, self.capability)

    async def do_authenticate(self, cmd, result):
        if not result:
            return ResponseNo(cmd.tag, b'Invalid authentication mechanism.')
        self.session = user = await self.login(result)
        if user:
            return ResponseOk(cmd.tag, b'Authentication successful.')
        return ResponseNo(cmd.tag, b'Invalid authentication credentials.')

    async def do_capability(self, cmd):
        response = ResponseOk(cmd.tag, b'Capabilities listed.')
        response.add_data(self.capability.to_response())
        return response

    async def do_noop(self, cmd):
        return ResponseOk(cmd.tag, b'NOOP completed.')

    def _get_mailbox_response_data(self, mbx, examine=False):
        data = [FlagsResponse(mbx.flags), ExistsResponse(mbx.exists),
                RecentResponse(mbx.recent),
                ResponseOk(b'*', b'Predicted next UID.',
                           UidNext(mbx.next_uid)),
                ResponseOk(b'*', b'UIDs valid.',
                           UidValidity(mbx.uid_validity))]
        if mbx.readonly or examine:
            code = ReadOnly()
            data.append(
                ResponseOk(b'*', b'Read-only mailbox.', PermanentFlags([])))
        else:
            code = ReadWrite()
            perm_flags = mbx.permanent_flags
            data.append(ResponseOk(b'*', b'Flags permitted.',
                                   PermanentFlags(perm_flags)))
        if mbx.first_unseen:
            data.append(ResponseOk(b'*', b'First unseen message.',
                                   Unseen(mbx.first_unseen)))
        return code, data

    async def do_select(self, cmd):
        try:
            mbx = await self.session.get_mailbox(cmd.mailbox)
        except MailboxNotFound:
            return ResponseNo(cmd.tag, b'Mailbox does not exist.')
        code, data = self._get_mailbox_response_data(mbx)
        self.selected = cmd.mailbox
        resp = ResponseOk(cmd.tag, b'Selected mailbox.', code)
        for data_part in data:
            resp.add_data(data_part)
        return resp

    async def do_examine(self, cmd):
        try:
            mbx = await self.session.get_mailbox(cmd.mailbox)
        except MailboxNotFound:
            return ResponseNo(cmd.tag, b'Mailbox does not exist.')
        code, data = self._get_mailbox_response_data(mbx, True)
        self.selected = cmd.mailbox
        resp = ResponseOk(cmd.tag, b'Examined mailbox.', code)
        for data_part in data:
            resp.add_data(data_part)
        return resp

    async def do_create(self, cmd):
        if cmd.mailbox == 'INBOX':
            return ResponseNo(cmd.tag, b'Cannot create INBOX.')
        try:
            await self.session.create_mailbox(cmd.mailbox)
        except MailboxConflict:
            return ResponseNo(cmd.tag, b'Mailbox already exists.')
        return ResponseOk(cmd.tag, b'Mailbox created successfully.')

    async def do_delete(self, cmd):
        if cmd.mailbox == 'INBOX':
            return ResponseNo(cmd.tag, b'Cannot delete INBOX.')
        try:
            await self.session.delete_mailbox(cmd.mailbox)
        except MailboxNotFound:
            return ResponseNo(cmd.tag, b'Mailbox not found.')
        except MailboxHasChildren:
            msg = b'Mailbox has inferior hierarchical names.'
            return ResponseNo(cmd.tag, msg)
        return ResponseOk(cmd.tag, b'Mailbox deleted successfully.')

    async def do_rename(self, cmd):
        if cmd.to_mailbox == b'INBOX':
            return ResponseNo(cmd.tag, b'Cannot rename to INBOX.')
        try:
            await self.session.rename_mailbox(cmd.from_mailbox, cmd.to_mailbox)
        except MailboxNotFound:
            return ResponseNo(cmd.tag, b'Mailbox not found.')
        except MailboxConflict:
            return ResponseNo(cmd.tag, b'Mailbox already exists.')
        return ResponseOk(cmd.tag, b'Mailbox renamed successfully.')

    async def do_status(self, cmd):
        try:
            mbx = await self.session.get_mailbox(cmd.mailbox)
        except MailboxNotFound:
            return ResponseNo(cmd.tag, b'Mailbox does not exist.')
        resp = ResponseOk(cmd.tag, b'STATUS completed.')
        status_list = List([])
        for status_item in cmd.status_list:
            status_list.value.append(status_item)
            if status_item.value == b'MESSAGES':
                status_list.value.append(Number(mbx.exists))
            elif status_item.value == b'RECENT':
                status_list.value.append(Number(mbx.recent))
            elif status_item.value == b'UNSEEN':
                status_list.value.append(Number(mbx.unseen))
            elif status_item.value == b'UIDNEXT':
                status_list.value.append(Number(mbx.next_uid))
            elif status_item.value == b'UIDVALIDITY':
                status_list.value.append(Number(mbx.uid_validity))
        status = Response(b'*', b'STATUS ' + bytes(cmd.mailbox_obj) + b' ' +
                          bytes(status_list))
        resp.add_data(status)
        return resp

    async def do_append(self, cmd):
        try:
            await self.session.append_message(
                cmd.mailbox, cmd.message, cmd.flag_set, cmd.when)
        except MailboxNotFound:
            return ResponseNo(cmd.tag, b'Mailbox does not exist.', TryCreate())
        except AppendFailure as exc:
            return ResponseNo(cmd.tag, bytes(str(exc), 'utf-8'))
        return ResponseOk(cmd.tag, b'APPEND completed.')

    async def do_subscribe(self, cmd):
        await self.session.subscribe(cmd.mailbox)
        return ResponseOk(cmd.tag, b'SUBSCRIBE completed.')

    async def do_unsubscribe(self, cmd):
        await self.session.unsubscribe(cmd.mailbox)
        return ResponseOk(cmd.tag, b'UNSUBSCRIBE completed.')

    async def do_list(self, cmd):
        mailboxes = await self.session.list_mailboxes(
            cmd.ref_name, cmd.filter)
        resp = ResponseOk(cmd.tag, b'LIST completed.')
        for mbx in mailboxes:
            resp.add_data(
                ListResponse(mbx.name, mbx.sep, marked=bool(mbx.recent)))
        return resp

    async def do_lsub(self, cmd):
        mailboxes = await self.session.list_mailboxes(
            cmd.ref_name, cmd.filter, subscribed=True)
        resp = ResponseOk(cmd.tag, b'LSUB completed.')
        for mbx in mailboxes:
            resp.add_data(LSubResponse(mbx.name, mbx.sep))
        return resp

    async def do_check(self, cmd):
        await self.session.check_mailbox(self.selected)
        return ResponseOk(cmd.tag, b'CHECK completed.')

    async def do_close(self, cmd):
        try:
            await self.session.expunge_mailbox(self.selected)
        except MailboxReadOnly:
            pass
        self.selected = None
        return ResponseOk(cmd.tag, b'CLOSE completed.')

    async def do_expunge(self, cmd):
        try:
            ids = await self.session.expunge_mailbox(self.selected)
        except MailboxReadOnly:
            return ResponseNo(cmd.tag, b'Mailbox is read-only.', ReadOnly())
        resp = ResponseOk(cmd.tag, b'EXPUNGE completed.')
        for id in ids:
            resp.add_data(ExpungeResponse(id))
        return resp

    async def do_copy(self, cmd):
        try:
            await self.session.copy_messages(
                self.selected, cmd.sequence_set, cmd.mailbox)
        except MailboxNotFound:
            return ResponseNo(cmd.tag, b'Mailbox does not exist.', TryCreate())
        return ResponseOk(cmd.tag, b'COPY completed.')

    async def do_fetch(self, cmd):
        messages = await self.session.fetch_messages(
            self.selected, cmd.sequence_set, cmd.attributes)
        resp = ResponseOk(cmd.tag, b'FETCH completed.')
        for msg_seq, msg in messages:
            fetch_data = {}
            for attr in cmd.attributes:
                if attr.attribute == b'UID':
                    fetch_data[attr] = Number(msg.uid)
                elif attr.attribute == b'FLAGS':
                    fetch_data[attr] = List(msg.flags)
                elif attr.attribute == b'INTERNALDATE':
                    fetch_data[attr] = DateTime(msg.internal_date)
                elif attr.attribute == b'ENVELOPE':
                    fetch_data[attr] = msg.get_envelope_structure()
                elif attr.attribute == b'BODYSTRUCTURE':
                    fetch_data[attr] = msg.get_body_structure(ext_data=True)
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
            resp.add_data(FetchResponse(msg_seq, fetch_data))
        return resp

    async def do_search(self, cmd):
        seqs = await self.session.search(self.selected, cmd.keys)
        resp = ResponseOk(cmd.tag, b'SEARCH completed.')
        resp.add_data(SearchResponse(seqs))
        return resp

    async def do_store(self, cmd):
        await self.session.update_flags(self.selected, cmd.sequence_set,
                                        cmd.flag_set, cmd.mode,
                                        silent=cmd.silent)
        resp = ResponseOk(cmd.tag, b'STORE completed.')
        attr_list = [self.flags_attr]
        if cmd.sequence_set.uid:
            attr_list.append(FetchAttribute(b'UID'))
        return resp

    async def do_logout(self, cmd):
        response = ResponseOk(cmd.tag, b'Logout successful.')
        response.add_data(ResponseBye(b'Logging out.'))
        raise CloseConnection(response)

    def _process_updates(self, cmd, resp, mailbox):
        if self.selected and self.selected.name == mailbox.name:
            send_expunge = not getattr(cmd, 'no_expunge_response', False)
        self.selected = mailbox

    async def _check_mailbox_updates(self, cmd, resp):
        send_expunge = not getattr(cmd, 'no_expunge_response', False)
        updates = await self.session.poll_mailbox(self.selected)
        expunge = updates.get('expunge', set())
        fetch = updates.get('fetch', {})
        self.expunge_buffer |= expunge
        if self.selected.exists > self.before_exists:
            exists = self.selected.exists + len(self.expunge_buffer)
            resp.add_data(ExistsResponse(exists))
            self.before_exists = self.selected.exists
        if self.selected.recent != self.before_recent:
            resp.add_data(RecentResponse(self.selected.recent))
            self.before_recent = self.selected.recent
        for msg_seq, msg_flags in fetch.items():
            fetch_data = {self.flags_attr: List(msg_flags)}
            resp.add_data(FetchResponse(msg_seq, fetch_data))
        if send_expunge and self.expunge_buffer:
            expunge_seqs = sorted(self.expunge_buffer, reverse=True)
            self.expunge_buffer.clear()
            for msg_seq in expunge_seqs:
                resp.add_data(ExpungeResponse(msg_seq))

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
        return await func(cmd)
