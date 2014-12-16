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

from .. import Space
from ..specials import Mailbox, SequenceSet
from . import CommandSelect, CommandNoArgs

__all__ = ['CheckCommand', 'CloseCommand', 'ExpungeCommand', 'CopyCommand',
           'FetchCommand', 'StoreCommand', 'UidCommand', 'SearchCommand']


class CheckCommand(CommandSelect, CommandNoArgs):
    command = b'CHECK'

CommandSelect._commands.append(CheckCommand)


class CloseCommand(CommandSelect, CommandNoArgs):
    command = b'CLOSE'

CommandSelect._commands.append(CloseCommand)


class ExpungeCommand(CommandSelect, CommandNoArgs):
    command = b'EXPUNGE'

CommandSelect._commands.append(ExpungeCommand)


class CopyCommand(CommandSelect):
    command = b'COPY'

    def __init__(self, tag, sequence_set, mailbox, uid=False):
        super(CopyCommand, self).__init__(tag)
        self.sequence_set = sequence_set
        self.mailbox = mailbox
        self.uid = uid

    @classmethod
    def _parse(cls, tag, buf, uid=False, **kwargs):
        _, buf = Space.parse(buf)
        sequence_set, buf = SequenceSet.parse(buf)
        _, buf = Space.parse(buf)
        mailbox, buf = Mailbox.parse(buf)
        _, buf = EndLine.parse(buf)
        return cls(tag, sequence_set.sequences, mailbox.value, uid=uid), buf

CommandSelect._commands.append(CopyCommand)


class FetchCommand(CommandSelect):
    command = b'FETCH'

    @classmethod
    def _parse(cls, tag, buf, **kwargs):
        raise NotImplementedError

CommandSelect._commands.append(FetchCommand)


class StoreCommand(CommandSelect):
    command = b'STORE'

    @classmethod
    def _parse(cls, tag, buf, **kwargs):
        raise NotImplementedError

CommandSelect._commands.append(StoreCommand)


class UidCommand(CommandSelect):
    command = b'UID'

    @classmethod
    def _parse(cls, tag, buf, **kwargs):
        for cmd in [CopyCommand, FetchCommand, SearchCommand, StoreCommand]:
            try:
                return cmd._parse(tag, buf, uid=True, **kwargs)
            except NotParseable:
                pass
        raise NotParseable(buf)

CommandSelect._commands.append(UidCommand)


class SearchCommand(CommandSelect):
    command = b'SEARCH'

    @classmethod
    def _parse(cls, tag, buf, **kwargs):
        raise NotImplementedError

CommandSelect._commands.append(SearchCommand)
