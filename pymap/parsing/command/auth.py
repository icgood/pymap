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

from .. import Space, EndLine
from ..specials import Mailbox
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

    @classmethod
    def _parse(cls, tag, buf, **kwargs):
        raise NotImplementedError

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

    @classmethod
    def _parse(cls, tag, buf, **kwargs):
        raise NotImplementedError

CommandAuth._commands.append(ListCommand)


class LSubCommand(CommandAuth):
    command = b'LSUB'

    @classmethod
    def _parse(cls, tag, buf, **kwargs):
        raise NotImplementedError

CommandAuth._commands.append(LSubCommand)


class RenameCommand(CommandAuth):
    command = b'RENAME'

    @classmethod
    def _parse(cls, tag, buf, **kwargs):
        raise NotImplementedError

CommandAuth._commands.append(RenameCommand)


class SelectCommand(CommandMailboxArg):
    command = b'SELECT'

CommandAuth._commands.append(SelectCommand)


class StatusCommand(CommandAuth):
    command = b'STATUS'

    @classmethod
    def _parse(cls, tag, buf, **kwargs):
        raise NotImplementedError

CommandAuth._commands.append(StatusCommand)


class SubscribeCommand(CommandMailboxArg):
    command = b'SUBSCRIBE'

CommandAuth._commands.append(SubscribeCommand)


class UnsubscribeCommand(CommandMailboxArg):
    command = b'UNSUBSCRIBE'

CommandAuth._commands.append(UnsubscribeCommand)
