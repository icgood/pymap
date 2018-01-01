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

import re
from datetime import datetime

from . import CommandAuth
from .. import NotParseable, UnexpectedType, Space, EndLine
from ..primitives import List, String, LiteralString
from ..specials import InvalidContent, Mailbox, DateTime, Flag, StatusAttribute

__all__ = ['AppendCommand', 'CreateCommand', 'DeleteCommand', 'ExamineCommand',
           'ListCommand', 'LSubCommand', 'RenameCommand', 'SelectCommand',
           'StatusCommand', 'SubscribeCommand', 'UnsubscribeCommand']


class CommandMailboxArg(CommandAuth):

    def __init__(self, tag, mailbox):
        super().__init__(tag)
        self.mailbox_obj = mailbox

    @property
    def mailbox(self):
        return str(self.mailbox_obj)

    @classmethod
    def _parse(cls, tag, buf, **kwargs):
        _, buf = Space.parse(buf)
        mailbox, buf = Mailbox.parse(buf)
        _, buf = EndLine.parse(buf)
        return cls(tag, mailbox), buf


class AppendCommand(CommandAuth):
    command = b'APPEND'

    def __init__(self, tag, mailbox, message, flag_list=None, when=None):
        super().__init__(tag)
        self.mailbox_obj = mailbox
        self.message = message
        self.flag_set = frozenset(flag.value for flag in (flag_list or []))
        self.when = when or datetime.now()

    @property
    def mailbox(self):
        return str(self.mailbox_obj)

    @classmethod
    def _parse(cls, tag, buf, **kwargs):
        _, buf = Space.parse(buf)
        mailbox, buf = Mailbox.parse(buf)
        _, buf = Space.parse(buf)
        try:
            flag_list, buf = List.parse(buf, list_expected=[Flag])
        except UnexpectedType:
            raise
        except NotParseable:
            flag_list = None
        else:
            flag_list = flag_list.value
            _, buf = Space.parse(buf)
        try:
            date_time, buf = DateTime.parse(buf)
        except InvalidContent:
            raise
        except NotParseable:
            date_time = None
        else:
            date_time = date_time.when
            _, buf = Space.parse(buf)
        message, buf = LiteralString.parse(buf, **kwargs)
        _, buf = EndLine.parse(buf)
        return cls(tag, mailbox, message.value, flag_list, date_time), buf

CommandAuth.register_command(AppendCommand)


class CreateCommand(CommandMailboxArg):
    command = b'CREATE'

CommandAuth.register_command(CreateCommand)


class DeleteCommand(CommandMailboxArg):
    command = b'DELETE'

CommandAuth.register_command(DeleteCommand)


class ExamineCommand(CommandMailboxArg):
    command = b'EXAMINE'

CommandAuth.register_command(ExamineCommand)


class ListCommand(CommandAuth):
    command = b'LIST'

    _list_mailbox_pattern = re.compile(br'[\x21\x23-\x27\x2A-\x5B'
                                       br'\x5D-\x7A\x7C\x7E]+')

    def __init__(self, tag, ref_name, filter):
        super().__init__(tag)
        self.ref_name = ref_name
        self.filter = filter

    @classmethod
    def _parse(cls, tag, buf, **kwargs):
        _, buf = Space.parse(buf)
        ref_name, buf = Mailbox.parse(buf)
        _, buf = Space.parse(buf)
        match = cls._list_mailbox_pattern.match(buf)
        if match:
            filter_raw = match.group(0)
            buf = buf[match.end(0):]
            filter = Mailbox.decode_name(filter_raw)
        else:
            filter_str, buf = String.parse(buf)
            filter = Mailbox.decode_name(filter_str.value)
        _, buf = EndLine.parse(buf)
        return cls(tag, ref_name.value, filter), buf

CommandAuth.register_command(ListCommand)


class LSubCommand(ListCommand):
    command = b'LSUB'

CommandAuth.register_command(LSubCommand)


class RenameCommand(CommandAuth):
    command = b'RENAME'

    def __init__(self, tag, from_mailbox, to_mailbox):
        super().__init__(tag)
        self.from_mailbox_obj = from_mailbox
        self.to_mailbox_obj = to_mailbox

    @property
    def from_mailbox(self):
        return str(self.from_mailbox_obj)

    @property
    def to_mailbox(self):
        return str(self.to_mailbox_obj)

    @classmethod
    def _parse(cls, tag, buf, **kwargs):
        _, buf = Space.parse(buf)
        from_mailbox, buf = Mailbox.parse(buf)
        _, buf = Space.parse(buf)
        to_mailbox, buf = Mailbox.parse(buf)
        _, buf = EndLine.parse(buf)
        return cls(tag, from_mailbox, to_mailbox), buf

CommandAuth.register_command(RenameCommand)


class SelectCommand(CommandMailboxArg):
    command = b'SELECT'

CommandAuth.register_command(SelectCommand)


class StatusCommand(CommandAuth):
    command = b'STATUS'

    def __init__(self, tag, mailbox, status_list):
        super().__init__(tag)
        self.mailbox_obj = mailbox
        self.status_list = status_list

    @property
    def mailbox(self):
        return str(self.mailbox_obj)

    @classmethod
    def _parse(cls, tag, buf, **kwargs):
        _, buf = Space.parse(buf)
        mailbox, buf = Mailbox.parse(buf)
        _, buf = Space.parse(buf)
        status_list, after = List.parse(buf, list_expected=[StatusAttribute])
        if not status_list.value:
            raise NotParseable(buf)
        _, buf = EndLine.parse(after)
        return cls(tag, mailbox, status_list.value), buf

CommandAuth.register_command(StatusCommand)


class SubscribeCommand(CommandMailboxArg):
    command = b'SUBSCRIBE'

CommandAuth.register_command(SubscribeCommand)


class UnsubscribeCommand(CommandMailboxArg):
    command = b'UNSUBSCRIBE'

CommandAuth.register_command(UnsubscribeCommand)
