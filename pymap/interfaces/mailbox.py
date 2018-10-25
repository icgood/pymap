from abc import abstractmethod
from typing import Optional, AbstractSet, FrozenSet
from typing_extensions import Protocol

from .message import Message
from ..flags import FlagOp
from ..parsing.specials import Flag
from ..selected import SelectedMailbox

__all__ = ['MailboxInterface']


class MailboxInterface(Protocol):
    """Describes a mailbox as it exists in an IMAP backend, whether or not it
    is currently selected.

    """

    def update_flags(self, selected: SelectedMailbox, message: Message,
                     flag_set: AbstractSet[Flag],
                     flag_op: FlagOp = FlagOp.REPLACE) \
            -> FrozenSet[Flag]:
        """Update the flags on a message in the mailbox. After this call,
        the ``message.permanent_flags`` set should be persisted by the
        backend.

        Args:
            selected: The active mailbox session.
            message: The message to set flags on.
            flag_set: The set of flags for the update operation.
            flag_op: The mode to change the flags.

        Returns:
            The resulting set of flags on the message.

        """
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """The name of the mailbox."""
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
