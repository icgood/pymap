"""Base implementations of the :mod:`pymap.interfaces.mailbox` interfaces."""

import random
import time
from typing import Optional, AbstractSet, FrozenSet

from .interfaces.mailbox import MailboxInterface
from .parsing.specials import Flag
from .parsing.specials.flag import Recent

__all__ = ['BaseMailbox']


class BaseMailbox(MailboxInterface):
    """Implements some of the basic functionality of a mailbox, for backends
    that wish to save themselves some trouble.

    Args:
        name: The name of the mailbox.
        permanent_flags: The permanent flags defined in the mailbox.
        session_flags: The session flags defined in the mailbox.
        readonly: If ``True``, the mailbox is read-only.
        uid_validity: The UID validity value for mailbox consistency.

    """

    def __init__(self, name: str,
                 permanent_flags: AbstractSet[Flag] = None,
                 session_flags: AbstractSet[Flag] = None,
                 readonly: bool = False,
                 uid_validity: int = 0) -> None:
        super().__init__()
        self._name = name
        self._readonly = readonly
        self._uid_validity = uid_validity
        self._permanent_flags: FrozenSet[Flag] = (
            frozenset(permanent_flags - {Recent})
            if permanent_flags else frozenset())
        self._session_flags: FrozenSet[Flag] = (
            frozenset((session_flags - self.permanent_flags) | {Recent})
            if session_flags else frozenset({Recent}))

    @classmethod
    def new_uid_validity(self) -> int:
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
    def uid_validity(self) -> int:
        return self._uid_validity

    @property
    def flags(self) -> FrozenSet[Flag]:
        return self.session_flags | self.permanent_flags

    @property
    def exists(self) -> int:
        """Number of total messages in the mailbox.

        Raises:
            NotImplementedError: Must be implemented by sub-class.

        """
        raise NotImplementedError

    @property
    def recent(self) -> int:
        """Number of recent messages in the mailbox.

        Raises:
            NotImplementedError: Must be implemented by sub-class.

        """
        raise NotImplementedError

    @property
    def unseen(self) -> int:
        """Number of unseen messages in the mailbox.

        Raises:
            NotImplementedError: Must be implemented by sub-class.

        """
        raise NotImplementedError

    @property
    def first_unseen(self) -> Optional[int]:
        """The sequence number of the first unseen message.

        Raises:
            NotImplementedError: Must be implemented by sub-class.

        """
        raise NotImplementedError

    @property
    def next_uid(self) -> int:
        """The predicted next message UID.

        Raises:
            NotImplementedError: Must be implemented by sub-class.

        """
        raise NotImplementedError
