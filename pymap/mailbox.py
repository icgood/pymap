"""Base implementation of the :mod:`pymap.interfaces.mailbox` interfaces."""

from __future__ import annotations

import random
import time
from collections.abc import Iterable
from typing import Optional, Final

from .interfaces.mailbox import MailboxInterface
from .parsing.specials import Flag, ObjectId
from .parsing.specials.flag import Recent

__all__ = ['MailboxSnapshot']


class MailboxSnapshot(MailboxInterface):
    """Implements the full functionality of a mailbox using entirely static
    arguments to the constructor. Backends can create and return a new
    mailbox snapshot every time a
    :class:`~pymap.interfaces.mailbox.MailboxInterface` is required.

    Args:
        mailbox_id: The mailbox ID.
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

    __slots__ = ['mailbox_id', 'readonly', 'uid_validity', 'permanent_flags',
                 'session_flags', 'exists', 'recent', 'unseen', 'first_unseen',
                 'next_uid']

    def __init__(self, mailbox_id: ObjectId, readonly: bool, uid_validity: int,
                 permanent_flags: Iterable[Flag],
                 session_flags: frozenset[Flag],
                 exists: int, recent: int, unseen: int,
                 first_unseen: Optional[int], next_uid: int) -> None:
        super().__init__()
        self.mailbox_id: Final = mailbox_id
        self.readonly: Final = readonly
        self.uid_validity: Final = uid_validity
        self.permanent_flags: Final = frozenset(permanent_flags) - {Recent}
        self.session_flags: Final = frozenset(session_flags) | {Recent}
        self.exists: Final = exists
        self.recent: Final = recent
        self.unseen: Final = unseen
        self.first_unseen: Final = first_unseen
        self.next_uid: Final = next_uid

    @classmethod
    def new_uid_validity(cls) -> int:
        """Generate a new UID validity value for a mailbox, where the first
        two bytes are time-based and the second two bytes are random.

        """
        time_part = int(time.time()) % 4096
        rand_part = random.randint(0, 1048576)
        return (time_part << 20) + rand_part

    @property
    def flags(self) -> frozenset[Flag]:
        return self.permanent_flags | self.session_flags
