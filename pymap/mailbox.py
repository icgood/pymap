"""Base implementation of the :mod:`pymap.interfaces.mailbox` interfaces."""

import random
import time
from typing import Optional, Iterable, FrozenSet

from .interfaces.mailbox import MailboxInterface
from .parsing.specials.flag import Flag, Recent

__all__ = ['MailboxSnapshot']


class MailboxSnapshot(MailboxInterface):
    """Implements the full functionality of a mailbox using entirely static
    arguments to the constructor. Backends can create and return a new
    mailbox snapshot every time a
    :class:`~pymap.interfaces.mailbox.MailboxInterface` is required.

    Args:
        name: The name of the mailbox.
        readonly: If ``True``, the mailbox is read-only.
        uid_validity: The UID validity value for mailbox consistency.
        permanent_flags: The permanent flags defined in the mailbox.
        session_flags: The session flags defined in the mailbox.
        exists: Number of total messages in the mailbox.
        recent: Number of recent messages in the mailbox.
        unseen: Number of unseen messages in the mailbox.
        first_unseen: The sequence number of the first unseen message.
        next_uid: The predicted next message UID.

    """

    def __init__(self, name: str, readonly: bool, uid_validity: int,
                 permanent_flags: Iterable[Flag],
                 session_flags: FrozenSet[Flag],
                 exists: int, recent: int, unseen: int,
                 first_unseen: Optional[int], next_uid: int) -> None:
        super().__init__()
        self._name = name
        self._readonly = readonly
        self._uid_validity = uid_validity
        self._permanent_flags = frozenset(permanent_flags) - {Recent}
        self._session_flags = frozenset(session_flags) | {Recent}
        self._exists = exists
        self._recent = recent
        self._unseen = unseen
        self._first_unseen = first_unseen
        self._next_uid = next_uid

    @classmethod
    def new_uid_validity(cls) -> int:
        """Generate a new UID validity value for a mailbox, where the first
        two bytes are time-based and the second two bytes are random.

        """
        time_part = int(time.time()) % 4096
        rand_part = random.randint(0, 1048576)
        return (time_part << 20) + rand_part

    @property
    def name(self) -> str:
        return self._name

    @property
    def readonly(self) -> bool:
        return self._readonly

    @property
    def permanent_flags(self) -> FrozenSet[Flag]:
        return self._permanent_flags

    @property
    def session_flags(self) -> FrozenSet[Flag]:
        return self._session_flags

    @property
    def flags(self) -> FrozenSet[Flag]:
        return self.permanent_flags | self.session_flags

    @property
    def uid_validity(self) -> int:
        return self._uid_validity

    @property
    def exists(self) -> int:
        return self._exists

    @property
    def recent(self) -> int:
        return self._recent

    @property
    def unseen(self) -> int:
        return self._unseen

    @property
    def first_unseen(self) -> Optional[int]:
        return self._first_unseen

    @property
    def next_uid(self) -> int:
        return self._next_uid
