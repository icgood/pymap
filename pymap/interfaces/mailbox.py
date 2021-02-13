
from __future__ import annotations

from abc import abstractmethod
from collections.abc import Sequence
from typing import Optional, Protocol

from ..parsing.specials import Flag, ObjectId

__all__ = ['MailboxInterface']


class MailboxInterface(Protocol):
    """Describes a mailbox as it exists in an IMAP backend, whether or not it
    is currently selected.

    """

    __slots__: Sequence[str] = []

    @property
    @abstractmethod
    def mailbox_id(self) -> ObjectId:
        """The mailbox object ID.

        This value must have no relationship to the mailbox name, e.g. a
        renamed mailbox should have the same ID but a deleted/re-created
        mailbox of the same name must have a different ID.

        See Also:
            `RFC 8474 4. <https://tools.ietf.org/html/rfc8474#section-4>`_

        """
        ...

    @property
    @abstractmethod
    def readonly(self) -> bool:
        """Whether the mailbox is read-only or read-write."""
        ...

    @property
    @abstractmethod
    def permanent_flags(self) -> frozenset[Flag]:
        """The permanent flags allowed in the mailbox."""
        ...

    @property
    @abstractmethod
    def session_flags(self) -> frozenset[Flag]:
        """The session flags allowed in the mailbox."""
        ...

    @property
    @abstractmethod
    def flags(self) -> frozenset[Flag]:
        """Set of all permanent and session flags available on the mailbox."""
        ...

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

    @property
    @abstractmethod
    def uid_validity(self) -> int:
        """The mailbox UID validity value."""
        ...
