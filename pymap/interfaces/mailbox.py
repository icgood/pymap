from abc import abstractmethod
from typing import Optional, FrozenSet
from typing_extensions import Protocol

from ..parsing.specials import Flag

__all__ = ['MailboxInterface']


class MailboxInterface(Protocol):
    """Describes a mailbox as it exists in an IMAP backend, whether or not it
    is currently selected.

    """

    @property
    @abstractmethod
    def guid(self) -> bytes:
        """The mailbox GUID. Typically a 128-bit hex bytestring.

        This value must have no relationship to the mailbox name, e.g. a
        renamed mailbox should have the same GUID but a deleted/re-created
        mailbox of the same name must have a different GUID.

        """
        ...

    @property
    @abstractmethod
    def readonly(self) -> bool:
        """Whether the mailbox is read-only or read-write."""
        ...

    @property
    @abstractmethod
    def permanent_flags(self) -> FrozenSet[Flag]:
        """The permanent flags allowed in the mailbox."""
        ...

    @property
    @abstractmethod
    def session_flags(self) -> FrozenSet[Flag]:
        """The session flags allowed in the mailbox."""
        ...

    @property
    @abstractmethod
    def flags(self) -> FrozenSet[Flag]:
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
