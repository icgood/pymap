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
from typing import Tuple, Sequence, FrozenSet

from . import CommandAuth
from .. import NotParseable, UnexpectedType, Space, EndLine, Buffer
from ..primitives import List, String, LiteralString
from ..specials import InvalidContent, Mailbox, DateTime, Flag, StatusAttribute

__all__ = ['AppendCommand', 'CreateCommand', 'DeleteCommand', 'ExamineCommand',
           'ListCommand', 'LSubCommand', 'RenameCommand', 'SelectCommand',
           'StatusCommand', 'SubscribeCommand', 'UnsubscribeCommand']


class CommandMailboxArg(CommandAuth):

    def __init__(self, tag, mailbox):
        super().__init__(tag)
        self.mailbox_obj = mailbox  # type: Mailbox

    @property
    def mailbox(self) -> str:
        return str(self.mailbox_obj)

    @classmethod
    def parse(cls, buf: Buffer, tag: bytes = None, **_) \
            -> Tuple['CommandMailboxArg', bytes]:
        _, buf = Space.parse(buf)
        mailbox, buf = Mailbox.parse(buf)
        _, buf = EndLine.parse(buf)
        return cls(tag, mailbox), buf


class AppendCommand(CommandAuth):
    command = b'APPEND'

    def __init__(self, tag, mailbox, message, flags=None, when=None):
        super().__init__(tag)
        self.mailbox_obj = mailbox  # type: Mailbox
        self.message = message  # type: bytes
        self.flag_set = frozenset(flags)  # type: FrozenSet[Flag]
        self.when = when or datetime.now()  # type: datetime

    @property
    def mailbox(self) -> str:
        return str(self.mailbox_obj)

    @classmethod
    def parse(cls, buf: Buffer, tag: bytes = None, **kwargs):
        _, buf = Space.parse(buf)
        mailbox, buf = Mailbox.parse(buf)
        _, buf = Space.parse(buf)
        try:
            flag_list, buf = List.parse(buf, list_expected=[Flag])
        except UnexpectedType:
            raise
        except NotParseable:
            flags = []
        else:
            flags = flag_list.value
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
        return cls(tag, mailbox, message.value, flags, date_time), buf


class CreateCommand(CommandMailboxArg):
    command = b'CREATE'


class DeleteCommand(CommandMailboxArg):
    command = b'DELETE'


class ExamineCommand(CommandMailboxArg):
    command = b'EXAMINE'


class ListCommand(CommandAuth):
    command = b'LIST'

    _list_mailbox_pattern = re.compile(br'[\x21\x23-\x27\x2A-\x5B'
                                       br'\x5D-\x7A\x7C\x7E]+')

    def __init__(self, tag, ref_name, filter_):
        super().__init__(tag)
        self.ref_name = ref_name  # type: str
        self.filter = filter_  # type: str

    @classmethod
    def parse(cls, buf: Buffer, tag: bytes = None, **_) \
            -> Tuple['ListCommand', bytes]:
        _, buf = Space.parse(buf)
        ref_name, buf = Mailbox.parse(buf)
        _, buf = Space.parse(buf)
        match = cls._list_mailbox_pattern.match(buf)
        if match:
            filter_raw = match.group(0)
            buf = buf[match.end(0):]
            filter_ = Mailbox.decode_name(filter_raw)
        else:
            filter_str, buf = String.parse(buf)
            filter_ = Mailbox.decode_name(filter_str.value)
        _, buf = EndLine.parse(buf)
        return cls(tag, ref_name.value, filter_), buf


class LSubCommand(ListCommand):
    command = b'LSUB'


class RenameCommand(CommandAuth):
    command = b'RENAME'

    def __init__(self, tag, from_mailbox, to_mailbox):
        super().__init__(tag)
        self.from_mailbox_obj = from_mailbox  # type: Mailbox
        self.to_mailbox_obj = to_mailbox  # type: Mailbox

    @property
    def from_mailbox(self) -> str:
        return str(self.from_mailbox_obj)

    @property
    def to_mailbox(self) -> str:
        return str(self.to_mailbox_obj)

    @classmethod
    def parse(cls, buf: Buffer, tag: bytes = None, **_) \
            -> Tuple['RenameCommand', bytes]:
        _, buf = Space.parse(buf)
        from_mailbox, buf = Mailbox.parse(buf)
        _, buf = Space.parse(buf)
        to_mailbox, buf = Mailbox.parse(buf)
        _, buf = EndLine.parse(buf)
        return cls(tag, from_mailbox, to_mailbox), buf


class SelectCommand(CommandMailboxArg):
    command = b'SELECT'


class StatusCommand(CommandAuth):
    command = b'STATUS'

    def __init__(self, tag, mailbox, status_list):
        super().__init__(tag)
        self.mailbox_obj = mailbox  # type: Mailbox
        self.status_list = status_list  # type: Sequence[StatusAttribute]

    @property
    def mailbox(self) -> str:
        return str(self.mailbox_obj)

    @classmethod
    def parse(cls, buf: Buffer, tag: bytes = None, **_) \
            -> Tuple['StatusCommand', bytes]:
        _, buf = Space.parse(buf)
        mailbox, buf = Mailbox.parse(buf)
        _, buf = Space.parse(buf)
        status_list, after = List.parse(buf, list_expected=[StatusAttribute])
        if not status_list.value:
            raise NotParseable(buf)
        _, buf = EndLine.parse(after)
        return cls(tag, mailbox, status_list.value), buf


class SubscribeCommand(CommandMailboxArg):
    command = b'SUBSCRIBE'


class UnsubscribeCommand(CommandMailboxArg):
    command = b'UNSUBSCRIBE'
