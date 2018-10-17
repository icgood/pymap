from typing import Optional, AbstractSet, FrozenSet

from .message import Message
from ..flags import FlagOp
from ..parsing.specials import Flag
from ..selected import SelectedMailbox

__all__ = ['MailboxInterface']


class MailboxInterface:
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
        raise NotImplementedError

    @property
    def name(self) -> str:
        """The name of the mailbox."""
        raise NotImplementedError

    @property
    def readonly(self) -> bool:
        """Whether the mailbox is read-only or read-write."""
        raise NotImplementedError

    @property
    def permanent_flags(self) -> FrozenSet[Flag]:
        """The permanent flags allowed in the mailbox."""
        raise NotImplementedError

    @property
    def session_flags(self) -> FrozenSet[Flag]:
        """The session flags allowed in the mailbox."""
        raise NotImplementedError

    @property
    def flags(self) -> FrozenSet[Flag]:
        """Set of all permanent and session flags available on the mailbox."""
        raise NotImplementedError

    @property
    def exists(self) -> int:
        """Number of total messages in the mailbox."""
        raise NotImplementedError

    @property
    def recent(self) -> int:
        """Number of recent messages in the mailbox."""
        raise NotImplementedError

    @property
    def unseen(self) -> int:
        """Number of unseen messages in the mailbox."""
        raise NotImplementedError

    @property
    def first_unseen(self) -> Optional[int]:
        """The sequence number of the first unseen message."""
        raise NotImplementedError

    @property
    def next_uid(self) -> int:
        """The predicted next message UID."""
        raise NotImplementedError

    @property
    def uid_validity(self) -> int:
        """The mailbox UID validity value."""
        raise NotImplementedError
