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

from datetime import datetime

from .. import NotParseable, UnexpectedType, Space, EndLine
from ..primitives import Atom, List, LiteralString
from ..specials import InvalidContent, Mailbox, DateTime, Flag, StatusAttribute
from . import CommandAuth

__all__ = ['AppendCommand', 'CreateCommand', 'DeleteCommand', 'ExamineCommand',
           'ListCommand', 'LSubCommand', 'RenameCommand', 'SelectCommand',
           'StatusCommand', 'SubscribeCommand', 'UnsubscribeCommand']


class CommandMailboxArg(CommandAuth):

    def __init__(self, tag, mailbox):
        super(CommandMailboxArg, self).__init__(tag)
        self.mailbox = mailbox

    @classmethod
    def _parse(cls, tag, buf, **kwargs):
        _, buf = Space.parse(buf)
        mailbox, buf = Mailbox.parse(buf)
        _, buf = EndLine.parse(buf)
        return cls(tag, mailbox.value), buf


class AppendCommand(CommandAuth):
    command = b'APPEND'

    def __init__(self, tag, mailbox, message, flag_list=None, when=None):
        super(AppendCommand, self).__init__(tag)
        self.mailbox = mailbox
        self.message = message
        self.flag_list = flag_list or []
        self.when = when or datetime.now()

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
        return cls(tag, mailbox.value, message.value,
                   flag_list, date_time), buf

CommandAuth._commands.append(AppendCommand)


class CreateCommand(CommandMailboxArg):
    command = b'CREATE'

CommandAuth._commands.append(CreateCommand)


class DeleteCommand(CommandMailboxArg):
    command = b'DELETE'

CommandAuth._commands.append(DeleteCommand)


class ExamineCommand(CommandMailboxArg):
    command = b'EXAMINE'

CommandAuth._commands.append(ExamineCommand)


class ListCommand(CommandAuth):
    command = b'LIST'

    def __init__(self, tag, mailbox, list_mailbox):
        super(ListCommand, self).__init__(tag)
        self.mailbox = mailbox
        self.list_mailbox = list_mailbox

    @classmethod
    def _parse(cls, tag, buf, **kwargs):
        _, buf = Space.parse(buf)
        mailbox, buf = Mailbox.parse(buf)
        _, buf = Space.parse(buf)
        list_mailbox, buf = Mailbox.parse(buf)
        _, buf = EndLine.parse(buf)
        return cls(tag, mailbox.value, list_mailbox.value), buf

CommandAuth._commands.append(ListCommand)


class LSubCommand(CommandAuth):
    command = b'LSUB'

    def __init__(self, tag, mailbox, list_mailbox):
        super(ListCommand, self).__init__(tag)
        self.mailbox = mailbox
        self.list_mailbox = list_mailbox

    @classmethod
    def _parse(cls, tag, buf, **kwargs):
        _, buf = Space.parse(buf)
        mailbox, buf = Mailbox.parse(buf)
        _, buf = Space.parse(buf)
        list_mailbox, buf = Mailbox.parse(buf)
        _, buf = EndLine.parse(buf)
        return cls(tag, mailbox.value, list_mailbox.value), buf

CommandAuth._commands.append(LSubCommand)


class RenameCommand(CommandAuth):
    command = b'RENAME'

    def __init__(self, tag, from_mailbox, to_mailbox):
        super(ListCommand, self).__init__(tag)
        self.mailbox = mailbox
        self.list_mailbox = list_mailbox

    @classmethod
    def _parse(cls, tag, buf, **kwargs):
        _, buf = Space.parse(buf)
        from_mailbox, buf = Mailbox.parse(buf)
        _, buf = Space.parse(buf)
        to_mailbox, buf = Mailbox.parse(buf)
        _, buf = EndLine.parse(buf)
        return cls(tag, from_mailbox.value, to_mailbox.value), buf

CommandAuth._commands.append(RenameCommand)


class SelectCommand(CommandMailboxArg):
    command = b'SELECT'

CommandAuth._commands.append(SelectCommand)


class StatusCommand(CommandAuth):
    command = b'STATUS'

    def __init__(self, tag, mailbox, status_list):
        super(StatusCommand, self).__init__(tag)
        self.mailbox = mailbox
        self.status_list = status_list

    @classmethod
    def _parse(cls, tag, buf, **kwargs):
        _, buf = Space.parse(buf)
        mailbox, buf = Mailbox.parse(buf)
        _, buf = Space.parse(buf)
        status_list, after = List.parse(buf, list_expected=[StatusAttribute])
        if not status_list.value:
            raise NotParseable(buf)
        _, buf = EndLine.parse(after)
        return cls(tag, mailbox.value, status_list.value), buf

CommandAuth._commands.append(StatusCommand)


class SubscribeCommand(CommandMailboxArg):
    command = b'SUBSCRIBE'

CommandAuth._commands.append(SubscribeCommand)


class UnsubscribeCommand(CommandMailboxArg):
    command = b'UNSUBSCRIBE'

CommandAuth._commands.append(UnsubscribeCommand)
