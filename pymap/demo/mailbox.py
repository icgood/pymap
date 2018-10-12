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

from copy import copy
from typing import TYPE_CHECKING, List, Optional, Dict, Tuple

from pymap.flag import Seen, Recent, Answered, Deleted, Draft, Flagged, \
    SessionFlags
from pymap.mailbox import MailboxSession, BaseMailbox
from .message import Message
from .state import State

__all__ = ['Mailbox']

if TYPE_CHECKING:
    from .session import Session


class _MailboxSession(MailboxSession):

    def __init__(self, name: str, *args, **kwargs) -> None:
        super().__init__(name, *args, **kwargs)
        State.mailboxes[name].sessions.add(self)

    def __copy__(self) -> 'MailboxSession':
        State.mailboxes[self.name].sessions.discard(self)
        return super().__copy__()


class Mailbox(BaseMailbox):
    SEP = b'.'
    FLAGS = {Seen, Recent, Answered, Deleted, Draft, Flagged}

    def __init__(self, name: str, session: 'Session') -> None:
        super().__init__(name, permanent_flags=self.FLAGS,
                         uid_validity=State.mailboxes[name].uid_validity)
        self.session = session
        self.messages: List[Message] = []
        self.uid_to_idx: Dict[int, int] = {}
        self.highest_uid: int = -1

    @classmethod
    def load(cls, name: str, session: 'Session', readonly: bool) \
            -> Tuple['Mailbox', MailboxSession]:
        mbx = cls(name, session)
        mbx.reset_messages()
        readonly = mbx.readonly or readonly
        session_flags = SessionFlags()
        if not readonly:
            recent = State.mailboxes[name].recent
            for msg in mbx.messages:
                if msg.uid in recent:
                    session_flags.add_recent(msg.uid)
            recent.clear()
        return mbx, _MailboxSession(name, mbx.exists, readonly, session_flags)

    @classmethod
    def get_snapshot(cls, name: str):
        return _MailboxSnapshot(name)

    def reset_messages(self):
        self.messages = copy(State.mailboxes[self.name].messages)
        self.uid_to_idx = {msg.uid: i for i, msg in enumerate(self.messages)}
        try:
            self.highest_uid = max(self.uid_to_idx.keys())
        except ValueError:
            self.highest_uid = None

    def _count_flag(self, flag):
        count = 0
        for msg in self.messages:
            if flag in msg.permanent_flags:
                count += 1
        return count

    @property
    def exists(self) -> int:
        return len(self.messages)

    @property
    def recent(self) -> int:
        return self._count_flag(Recent)

    @property
    def unseen(self) -> int:
        return self.exists - self._count_flag(Seen)

    @property
    def first_unseen(self) -> Optional[int]:
        for i, msg in enumerate(self.messages):
            if Seen not in msg.permanent_flags:
                return i + 1
        return None

    @property
    def next_uid(self) -> int:
        return State.mailboxes[self.name].next_uid


class _MailboxSnapshot(BaseMailbox):

    def __init__(self, name: str) -> None:
        super().__init__(
            name=name,
            readonly=True,
            permanent_flags=Mailbox.FLAGS,
            uid_validity=State.mailboxes[name].uid_validity)
        messages = copy(State.mailboxes[name].messages)
        self._exists = len(messages)
        self._recent = len(State.mailboxes[name].recent)
        self._unseen = 0
        self._first_unseen = 0
        for msg_seq, msg in enumerate(messages):
            if Seen not in msg.permanent_flags:
                self._unseen += 1
                self._first_unseen = self._first_unseen or (msg_seq + 1)
        self._next_uid = State.mailboxes[self.name].next_uid

    @property
    def exists(self):
        return self._exists

    @property
    def recent(self):
        return self._recent

    @property
    def unseen(self):
        return self._unseen

    @property
    def first_unseen(self):
        return self._first_unseen

    @property
    def next_uid(self):
        return self._next_uid

    @property
    def updates(self):
        return {}
