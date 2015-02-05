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

import asyncio
from socket import getfqdn

from pymap.exceptions import *  # NOQA

from pymap.core import PymapError
from pymap.parsing.primitives import List, Number
from pymap.parsing.specials import FetchAttribute
from pymap.parsing.command import CommandAuth, CommandNonAuth, CommandSelect
from pymap.parsing.response import *  # NOQA
from pymap.parsing.response.code import *  # NOQA
from pymap.parsing.response.specials import *  # NOQA

__all__ = ['CloseConnection', 'ConnectionState']

fqdn = getfqdn().encode('ascii')


class CloseConnection(PymapError):
    """Raised when the connection should be closed immediately after sending
    the provided response.

    :param response: The response to send before closing the connection.
    :type response: :class:`~pymap.parsing.response.Response`

    """

    def __init__(self, response):
        super().__init__()
        self.response = response


class ConnectionState(object):

    flags_attr = FetchAttribute(b'FLAGS')

    def __init__(self, transport, backends):
        super().__init__()
        self.transport = transport
        self.backends = backends
        self.user = None
        self.selected = None
        self.capability = Capability([])

    @asyncio.coroutine
    def do_greeting(self):
        return ResponseOk(b'*', b'Server ready ' + fqdn, self.capability)

    @asyncio.coroutine
    def do_authenticate(self, cmd, result):
        for login in self.backends:
            self.user = user = yield from login(result)
            if user:
                return ResponseOk(cmd.tag, b'Authentication successful.')
        return ResponseNo(cmd.tag, b'Invalid authentication credentials.')

    @asyncio.coroutine
    def do_capability(self, cmd):
        response = ResponseOk(cmd.tag, b'Capabilities listed.')
        response.add_data(self.capability.to_response())
        return response

    @asyncio.coroutine
    def do_noop(self, cmd):
        return ResponseOk(cmd.tag, b'NOOP completed.')

    def _get_mailbox_response_data(self, mbx, examine=False):
        data = [FlagsResponse(mbx.flags),
                ExistsResponse(mbx.exists),
                RecentResponse(mbx.recent),
                ResponseOk(b'*', b'Predicted next UID.',
                           UidNext(mbx.next_uid)),
                ResponseOk(b'*', b'UIDs valid.',
                           UidValidity(mbx.uid_validity))]
        if mbx.readonly or examine:
            code = ReadOnly()
            data.append(ResponseOk(b'*', b'Read-only mailbox.',
                                   PermanentFlags([])))
        else:
            code = ReadWrite()
            perm_flags = mbx.permanent_flags
            data.append(ResponseOk(b'*', b'Flags permitted.',
                                   PermanentFlags(perm_flags)))
        return code, data

    @asyncio.coroutine
    def do_select(self, cmd):
        try:
            mbx = yield from self.user.get_mailbox(cmd.mailbox)
        except MailboxNotFound:
            return ResponseNo(cmd.tag, b'Mailbox does not exist.')
        self.selected = mbx
        code, data = self._get_mailbox_response_data(mbx)
        resp = ResponseOk(cmd.tag, b'Selected mailbox.', code)
        for data_part in data:
            resp.add_data(data_part)
        return resp

    @asyncio.coroutine
    def do_examine(self, cmd):
        try:
            mbx = yield from self.user.get_mailbox(cmd.mailbox)
        except MailboxNotFound:
            return ResponseNo(cmd.tag, b'Mailbox does not exist.')
        code, data = self._get_mailbox_response_data(mbx, True)
        resp = ResponseOk(cmd.tag, b'Examined mailbox.', code)
        for data_part in data:
            resp.add_data(data_part)
        return resp

    @asyncio.coroutine
    def do_create(self, cmd):
        try:
            yield from self.user.create_mailbox(cmd.mailbox)
        except MailboxConflict:
            return ResponseNo(cmd.tag, b'Mailbox already exists.')
        return ResponseOk(cmd.tag, b'Mailbox created successfully.')

    @asyncio.coroutine
    def do_delete(self, cmd):
        if cmd.mailbox == b'INBOX':
            return ResponseNo(cmd.tag, b'Cannot delete INBOX.')
        try:
            yield from self.user.delete_mailbox(cmd.mailbox)
        except MailboxNotFound:
            return ResponseNo(cmd.tag, b'Mailbox not found.')
        except MailboxHasChildren:
            msg = b'Mailbox has inferior hierarchical names.'
            return ResponseNo(cmd.tag, msg)
        return responseOk(cmd.tag, b'Mailbox deleted successfully.')

    @asyncio.coroutine
    def do_rename(self, cmd):
        if cmd.to_mailbox == b'INBOX':
            return ResponseNo(cmd.tag, b'Cannot rename to INBOX.')
        try:
            yield from self.user.rename_mailbox(cmd.from_mailbox,
                                                cmd.to_mailbox)
        except MailboxNotFound:
            return ResponseNo(cmd.tag, b'Mailbox not found.')
        except MailboxConflict:
            return ResponseNo(cmd.tag, b'Mailbox already exists.')
        return ResponseOk(cmd.tag, b'Mailbox renamed successfully.')

    @asyncio.coroutine
    def do_status(self, cmd):
        try:
            mbx = yield from self.user.get_mailbox(cmd.mailbox)
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
            elif status_item.value == b'UIDNEXT':
                status_list.value.append(Number(mbx.next_uid))
            elif status_item.value == b'UIDVALIDITY':
                status_list.value.append(Number(mbx.uid_validity))
            elif status_item.value == b'UNSEEN':
                status_list.value.append(Number(mbx.unseen))
        status = Response(b'*', b'STATUS ' + cmd.mailbox + b' ' +
                          bytes(status_list))
        resp.add_data(status)
        return resp

    @asyncio.coroutine
    def do_append(self, cmd):
        try:
            flag_list = [flag.value for flag in cmd.flag_list]
            yield from self.user.append_message(cmd.mailbox, cmd.message,
                                                flag_list, cmd.when)
        except MailboxNotFound:
            return ResponseNo(cmd.tag, b'Mailbox does not exist.', TryCreate())
        except AppendFailure as exc:
            return ResponseNo(cmd.tag, bytes(str(exc), 'utf-8'))
        return ResponseOk(cmd.tag, b'APPEND completed.')

    @asyncio.coroutine
    def do_subscribe(self, cmd):
        yield from self.user.subscribe(cmd.mailbox)
        return ResponseOk(cmd.tag, b'SUBSCRIBE completed.')

    @asyncio.coroutine
    def do_unsubscribe(self, cmd):
        yield from self.user.unsubscribe(cmd.mailbox)
        return ResponseOk(cmd.tag, b'UNSUBSCRIBE completed.')

    def _mailbox_matches(self, name, sep, ref_name, filter):
        return True

    @asyncio.coroutine
    def do_list(self, cmd):
        mailboxes = yield from self.user.list_mailboxes()
        resp = ResponseOk(cmd.tag, b'LIST completed.')
        for mbx in mailboxes:
            if self._mailbox_matches(mbx.name, mbx.sep,
                                     cmd.ref_name, cmd.filter):
                resp.add_data(ListResponse(mbx.name, mbx.sep,
                                           marked=mbx.marked))
        return resp

    @asyncio.coroutine
    def do_lsub(self, cmd):
        mailboxes = yield from self.user.list_mailboxes(subscribed=True)
        resp = ResponseOk(cmd.tag, b'LSUB completed.')
        for mbx in mailboxes:
            if self._mailbox_matches(mbx.name, mbx.sep,
                                     cmd.ref_name, cmd.filter):
                resp.add_data(LSubResponse(mbx.name, mbx.sep))
        return resp

    @asyncio.coroutine
    def _get_messages(self, messages, by_uid):
        if by_uid:
            return (yield from self.selected.get_messages_by_uid(messages))
        else:
            return (yield from self.selected.get_messages_by_seq(messages))

    @asyncio.coroutine
    def do_check(self, cmd):
        return ResponseOk(cmd.tag, b'CHECK completed.')

    @asyncio.coroutine
    def do_close(self, cmd):
        try:
            yield from self.selected.expunge()
        except MailboxReadOnly:
            pass
        self.selected = None
        return ResponseOk(cmd.tag, b'CLOSE completed.')

    @asyncio.coroutine
    def do_expunge(self, cmd):
        try:
            expunged = yield from self.selected.expunge()
        except MailboxReadOnly:
            return ResponseNo(cmd.tag, b'Mailbox is read-only.', ReadOnly())
        resp = ResponseOk(cmd.tag, b'EXPUNGE completed.')
        for seq in expunged:
            resp.add_data(ExpungeResponse(seq))
        return resp

    @asyncio.coroutine
    def do_copy(self, cmd):
        messages = yield from self._get_messages(cmd.sequence_set.sequences,
                                                 cmd.uid)
        try:
            yield from self.selected.copy(messages, cmd.mailbox)
        except MailboxNotFound:
            return ResponseNo(cmd.tag, b'Mailbox does not exist.', TryCreate())
        return ResponseOk(cmd.tag, b'COPY completed.')

    @asyncio.coroutine
    def do_fetch(self, cmd):
        messages = yield from self._get_messages(cmd.sequence_set.sequences,
                                                 cmd.uid)
        resp = ResponseOk(cmd.tag, b'FETCH completed.')
        for msg in messages:
            fetch_data = yield from msg.fetch(cmd.attributes)
            resp.add_data(FetchResponse(msg.seq, fetch_data))
        return resp

    @asyncio.coroutine
    def do_search(self, cmd):
        messages = yield from self.selected.search(cmd.keys)
        resp = ResponseOk(cmd.tag, b'SEARCH completed.')
        if cmd.uid:
            seqs = [msg.uid for msg in messages]
        else:
            seqs = [msg.seq for msg in messages]
        resp.add_data(SearchResponse(seqs))
        return resp

    @asyncio.coroutine
    def do_store(self, cmd):
        messages = yield from self._get_messages(cmd.sequence_set.sequences,
                                                 cmd.uid)
        flag_list = [flag.value for flag in cmd.flag_list.value]
        yield from self.selected.update_flags(messages, flag_list, cmd.mode)
        resp = ResponseOk(cmd.tag, b'STORE completed.')
        if not cmd.silent:
            for msg in messages:
                fetch_data = yield from msg.fetch([self.flags_attr])
                resp.add_data(FetchResponse(msg.seq, fetch_data))
        return resp

    @asyncio.coroutine
    def do_logout(self, cmd):
        response = ResponseOk(cmd.tag, b'Logout successful.')
        response.add_data(ResponseBye(b'Logging out.'))
        raise CloseConnection(response)

    @asyncio.coroutine
    def _check_mailbox_updates(self, cmd, resp):
        send_expunge = not getattr(cmd, 'no_expunge_response', False)
        updates = yield from self.selected.poll()
        if 'exists' in updates:
            resp.add_data(ExistsResponse(updates['exists']))
        if 'recent' in updates:
            resp.add_data(RecentResponse(updates['recent']))
        if 'expunge' in updates and send_expunge:
            for seq in updates['expunge']:
                resp.add_data(ExpungeResponse(seq))
        if 'fetch' in updates:
            for msg in updates['fetch']:
                fetch_data = yield from msg.fetch([self.flags_attr])
                resp.add_data(FetchResponse(msg.seq, fetch_data))

    @asyncio.coroutine
    def do_command(self, cmd):
        if self.user and isinstance(cmd, CommandNonAuth):
            msg = cmd.command + b': Already authenticated.'
            return ResponseBad(cmd.tag, msg)
        elif not self.user and isinstance(cmd, CommandAuth):
            msg = cmd.command + b': Must authenticate first.'
            return ResponseBad(cmd.tag, msg)
        elif not self.selected and isinstance(cmd, CommandSelect):
            msg = cmd.command + b': Must select a mailbox first.'
            return ResponseBad(cmd.tag, msg)
        pre_selected = self.selected
        func_name = 'do_' + str(cmd.command, 'ascii').lower()
        try:
            func = getattr(self, func_name)
        except AttributeError:
            return ResponseNo(cmd.tag, cmd.command + b': Not Implemented')
        resp = yield from func(cmd)
        if self.selected and pre_selected:
            yield from self._check_mailbox_updates(cmd, resp)
        return resp
