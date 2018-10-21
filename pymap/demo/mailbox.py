from copy import copy
from typing import List, Optional, Dict, Tuple

from pymap.flags import SessionFlags
from pymap.mailbox import BaseMailbox
from pymap.parsing.specials.flag import Seen, Recent, Answered, Deleted, \
    Draft, Flagged
from pymap.selected import SelectedMailbox
from .message import Message
from .state import State

__all__ = ['Mailbox']


class _SelectedMailbox(SelectedMailbox):

    def __init__(self, name: str, *args, **kwargs) -> None:
        super().__init__(name, *args, **kwargs)
        State.mailboxes[name].sessions.add(self)

    def __copy__(self) -> 'SelectedMailbox':
        State.mailboxes[self.name].sessions.discard(self)
        return super().__copy__()


class Mailbox(BaseMailbox):
    SEP = b'.'
    FLAGS = {Seen, Recent, Answered, Deleted, Draft, Flagged}

    def __init__(self, name: str) -> None:
        super().__init__(name, permanent_flags=self.FLAGS,
                         uid_validity=State.mailboxes[name].uid_validity)
        self.messages: List[Message] = []
        self.uid_to_idx: Dict[int, int] = {}
        self.highest_seq: int = 0
        self.highest_uid: int = 0

    @classmethod
    def load(cls, name: str, readonly: bool) \
            -> Tuple['Mailbox', _SelectedMailbox]:
        mbx = cls(name)
        mbx.reset_messages()
        readonly = mbx.readonly or readonly
        session_flags = SessionFlags()
        if not readonly:
            recent = State.mailboxes[name].recent
            for msg in mbx.messages:
                if msg.uid in recent:
                    session_flags.add_recent(msg.uid)
            recent.clear()
        return mbx, _SelectedMailbox(name, mbx.exists, readonly, session_flags)

    @classmethod
    def get_snapshot(cls, name: str):
        return _MailboxSnapshot(name)

    def reset_messages(self):
        self.messages = copy(State.mailboxes[self.name].messages)
        self.uid_to_idx = {msg.uid: i for i, msg in enumerate(self.messages)}
        try:
            self.highest_seq = len(self.messages)
            self.highest_uid = max(self.uid_to_idx.keys())
        except ValueError:
            self.highest_seq = 0
            self.highest_uid = 0

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
