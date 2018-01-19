# Copyright (c) 2015 Ian C. Good
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
from typing import List

from pymap.interfaces import MailboxState
from pymap.updates import MailboxUpdates
from .message import Message
from .state import State

__all__ = ['Mailbox']


class Mailbox(MailboxState):

    sep = b'.'
    _FLAGS = {br'\Seen', br'\Recent', br'\Answered', br'\Deleted',
              br'\Draft', br'\Flagged'}

    def __init__(self, name: str):
        super().__init__(
            flags=self._FLAGS,
            permanent_flags=self._FLAGS,
            uid_validity=State.mailboxes[name].uid_validity,
        )
        self.name = name  # type: str
        self.messages = None  # type: List[Message]
        self.updates = MailboxUpdates()  # type: MailboxUpdates
        self.reset_messages()

    def reset_messages(self):
        self.messages = copy(State.mailboxes[self.name].messages)
        self.updates.exists = self.exists
        self.updates.recent = frozenset(*State.mailboxes[self.name].recent)

    @property
    def exists(self) -> int:
        return len(self.messages)

    @property
    def recent(self) -> int:
        return len(self.updates.recent)

    @property
    def unseen(self) -> int:
        unseen = 0
        for msg in self.messages:
            if br'\Seen' not in msg.flags:
                unseen += 1
        return unseen

    @property
    def first_unseen(self) -> int:
        for i, msg in enumerate(self.messages):
            if br'\Seen' not in msg.flags:
                return i + 1

    @property
    def next_uid(self) -> int:
        return State.mailboxes[self.name].next_uid
