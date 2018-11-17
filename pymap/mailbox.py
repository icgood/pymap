"""Base implementations of the :mod:`pymap.interfaces.mailbox` interfaces."""

import random
import time
from abc import abstractmethod, ABCMeta
from typing import Optional, Iterable, FrozenSet

from .interfaces.mailbox import MailboxInterface
from .parsing.specials import Flag
from .parsing.specials.flag import Recent

__all__ = ['BaseMailbox']


class BaseMailbox(MailboxInterface, metaclass=ABCMeta):
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
                 permanent_flags: Iterable[Flag] = None,
                 session_flags: Iterable[Flag] = None,
                 readonly: bool = False,
                 uid_validity: int = 0) -> None:
        super().__init__()
        self._name = name
        self._readonly = readonly
        self._uid_validity = uid_validity
        self._permanent_flags: FrozenSet[Flag] = (
            frozenset(permanent_flags) - {Recent}
            if permanent_flags else frozenset())
        self._session_flags: FrozenSet[Flag] = (
            (frozenset(session_flags) - self.permanent_flags) | {Recent}
            if session_flags else frozenset({Recent}))

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
    def uid_validity(self) -> int:
        return self._uid_validity

    @property
    def flags(self) -> FrozenSet[Flag]:
        return self.session_flags | self.permanent_flags

    @property
    @abstractmethod
    def exists(self) -> int:
        """Number of total messages in the mailbox."""
        ...

    @property
    @abstractmethod
    def recent(self) -> int:
        """Number of recent messages in the mailbox."""
        ...

    @property
    @abstractmethod
    def unseen(self) -> int:
        """Number of unseen messages in the mailbox."""
        ...

    @property
    @abstractmethod
    def first_unseen(self) -> Optional[int]:
        """The sequence number of the first unseen message."""
        ...

    @property
    @abstractmethod
    def next_uid(self) -> int:
        """The predicted next message UID."""
        ...
