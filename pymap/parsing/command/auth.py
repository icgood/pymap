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

import re
from datetime import datetime
from typing import cast, Tuple, Sequence, Iterable

from . import CommandAuth
from .. import NotParseable, UnexpectedType, Space, EndLine, Params, \
    InvalidContent
from ..primitives import ListP, String, LiteralString
from ..specials import Mailbox, DateTime, Flag, StatusAttribute

__all__ = ['AppendCommand', 'CreateCommand', 'DeleteCommand', 'ExamineCommand',
           'ListCommand', 'LSubCommand', 'RenameCommand', 'SelectCommand',
           'StatusCommand', 'SubscribeCommand', 'UnsubscribeCommand']


class CommandMailboxArg(CommandAuth):

    def __init__(self, tag: bytes, mailbox: Mailbox) -> None:
        super().__init__(tag)
        self.mailbox_obj = mailbox

    @property
    def mailbox(self) -> str:
        return str(self.mailbox_obj)

    @classmethod
    def parse(cls, buf: bytes, params: Params) \
            -> Tuple['CommandMailboxArg', bytes]:
        _, buf = Space.parse(buf, params)
        mailbox, buf = Mailbox.parse(buf, params)
        _, buf = EndLine.parse(buf, params)
        return cls(params.tag, mailbox), buf


class AppendCommand(CommandAuth):
    command = b'APPEND'

    def __init__(self, tag: bytes, mailbox: Mailbox, message: bytes,
                 flags: Iterable[Flag] = None, when: datetime = None) -> None:
        super().__init__(tag)
        self.mailbox_obj = mailbox
        self.message = message
        self.flag_set = frozenset(flags or [])
        self.when: datetime = when or datetime.now()

    @property
    def mailbox(self) -> str:
        return str(self.mailbox_obj)

    @classmethod
    def parse(cls, buf: bytes, params: Params) \
            -> Tuple['AppendCommand', bytes]:
        _, buf = Space.parse(buf, params)
        mailbox, buf = Mailbox.parse(buf, params)
        _, buf = Space.parse(buf, params)
        try:
            params_copy = params.copy(list_expected=[Flag])
            flag_list, buf = ListP.parse(buf, params_copy)
        except UnexpectedType:
            raise
        except NotParseable:
            flags = []  # type: ignore
        else:
            flags = flag_list.value
            _, buf = Space.parse(buf, params)
        try:
            date_time_p, buf = DateTime.parse(buf, params)
        except InvalidContent:
            raise
        except NotParseable:
            date_time = None
        else:
            date_time = date_time_p.value
            _, buf = Space.parse(buf, params)
        message, buf = LiteralString.parse(buf, params)
        _, buf = EndLine.parse(buf, params)
        return cls(params.tag, mailbox, message.value, flags, date_time), buf


class CreateCommand(CommandMailboxArg):
    command = b'CREATE'


class DeleteCommand(CommandMailboxArg):
    command = b'DELETE'


class ListCommand(CommandAuth):
    command = b'LIST'

    _list_mailbox_pattern = re.compile(br'[\x21\x23-\x27\x2A-\x5B'
                                       br'\x5D-\x7A\x7C\x7E]+')

    def __init__(self, tag: bytes, ref_name: str, filter_: str) -> None:
        super().__init__(tag)
        self.ref_name = ref_name
        self.filter = filter_

    @classmethod
    def parse(cls, buf: bytes, params: Params) -> Tuple['ListCommand', bytes]:
        _, buf = Space.parse(buf, params)
        ref_name, buf = Mailbox.parse(buf, params)
        _, buf = Space.parse(buf, params)
        match = cls._list_mailbox_pattern.match(buf)
        if match:
            filter_raw = match.group(0)
            buf = buf[match.end(0):]
            filter_ = Mailbox.decode_name(filter_raw)
        else:
            filter_str, buf = String.parse(buf, params)
            filter_ = Mailbox.decode_name(filter_str.value)
        _, buf = EndLine.parse(buf, params)
        return cls(params.tag, ref_name.value, filter_), buf


class LSubCommand(ListCommand):
    command = b'LSUB'


class RenameCommand(CommandAuth):
    command = b'RENAME'

    def __init__(self, tag: bytes, from_mailbox: Mailbox,
                 to_mailbox: Mailbox) -> None:
        super().__init__(tag)
        self.from_mailbox_obj = from_mailbox
        self.to_mailbox_obj = to_mailbox

    @property
    def from_mailbox(self) -> str:
        return str(self.from_mailbox_obj)

    @property
    def to_mailbox(self) -> str:
        return str(self.to_mailbox_obj)

    @classmethod
    def parse(cls, buf: bytes, params: Params) \
            -> Tuple['RenameCommand', bytes]:
        _, buf = Space.parse(buf, params)
        from_mailbox, buf = Mailbox.parse(buf, params)
        _, buf = Space.parse(buf, params)
        to_mailbox, buf = Mailbox.parse(buf, params)
        _, buf = EndLine.parse(buf, params)
        return cls(params.tag, from_mailbox, to_mailbox), buf


class SelectCommand(CommandMailboxArg):
    command = b'SELECT'


class ExamineCommand(SelectCommand):
    command = b'EXAMINE'


class StatusCommand(CommandAuth):
    command = b'STATUS'

    def __init__(self, tag: bytes, mailbox: Mailbox,
                 status_list: Sequence[StatusAttribute]) -> None:
        super().__init__(tag)
        self.mailbox_obj = mailbox
        self.status_list = status_list

    @property
    def mailbox(self) -> str:
        return str(self.mailbox_obj)

    @classmethod
    def parse(cls, buf: bytes, params: Params) \
            -> Tuple['StatusCommand', bytes]:
        _, buf = Space.parse(buf, params)
        mailbox, buf = Mailbox.parse(buf, params)
        _, buf = Space.parse(buf, params)
        params_copy = params.copy(list_expected=[StatusAttribute])
        status_list_p, after = ListP.parse(buf, params_copy)
        if not status_list_p.value:
            raise NotParseable(buf)
        _, buf = EndLine.parse(after, params)
        status_list = cast(Sequence[StatusAttribute], status_list_p.value)
        return cls(params.tag, mailbox, status_list), buf


class SubscribeCommand(CommandMailboxArg):
    command = b'SUBSCRIBE'


class UnsubscribeCommand(CommandMailboxArg):
    command = b'UNSUBSCRIBE'
