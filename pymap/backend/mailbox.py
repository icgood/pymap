
from __future__ import annotations

from abc import abstractmethod
from collections.abc import Iterable, Sequence, AsyncIterable
from typing import TypeVar, Optional, Protocol

from pymap.concurrent import Event
from pymap.flags import FlagOp
from pymap.interfaces.message import MessageT_co, CachedMessage
from pymap.listtree import ListTree
from pymap.mailbox import MailboxSnapshot
from pymap.parsing.message import AppendMessage
from pymap.parsing.specials import ObjectId, SequenceSet
from pymap.parsing.specials.flag import get_system_flags, Flag, Deleted, Recent
from pymap.selected import SelectedSet, SelectedMailbox

__all__ = ['MailboxDataT', 'MailboxDataT_co',
           'MailboxDataInterface', 'MailboxSetInterface']

#: Type variable with an upper bound of :class:`MailboxDataInterface`.
MailboxDataT = TypeVar('MailboxDataT', bound='MailboxDataInterface')

#: Covariant type variable with an upper bound of
#: :class:`MailboxDataInterface`.
MailboxDataT_co = TypeVar('MailboxDataT_co', bound='MailboxDataInterface',
                          covariant=True)


class MailboxDataInterface(Protocol[MessageT_co]):
    """Manages the messages and metadata associated with a single mailbox."""

    @property
    @abstractmethod
    def mailbox_id(self) -> ObjectId:
        """The mailbox object ID.

        See Also:
            :attr:`~pymap.interfaces.mailbox.MailboxInterface.mailbox_id`

        """
        ...

    @property
    @abstractmethod
    def readonly(self) -> bool:
        """Whether the mailbox is read-only or read-write."""
        ...

    @property
    @abstractmethod
    def uid_validity(self) -> int:
        """The mailbox UID validity value."""
        ...

    @property
    def permanent_flags(self) -> frozenset[Flag]:
        """The permanent flags allowed in the mailbox."""
        return get_system_flags() - {Recent}

    @property
    def session_flags(self) -> frozenset[Flag]:
        """The session flags allowed in the mailbox."""
        return frozenset({Recent})

    @property
    @abstractmethod
    def selected_set(self) -> SelectedSet:
        """The set of selected mailbox sessions currently active."""
        ...

    @abstractmethod
    async def update_selected(self, selected: SelectedMailbox, *,
                              wait_on: Event = None) -> SelectedMailbox:
        """Populates and returns the selected mailbox object with the state
        needed to discover updates.

        Args:
            selected: the selected mailbox object.
            wait_on: If given, block until this event signals or mailbox
                activity occurs.

        """
        ...

    @abstractmethod
    async def append(self, append_msg: AppendMessage, *,
                     recent: bool = False) -> MessageT_co:
        """Adds a new message to the end of the mailbox, returning a copy of
        message with its assigned UID.

        Args:
            append_msg: The new message data.
            recent: True if the message should be marked recent.

        """
        ...

    @abstractmethod
    async def copy(self: MailboxDataT, uid: int, destination: MailboxDataT, *,
                   recent: bool = False) -> Optional[int]:
        """Copies a message, if it exists, from this mailbox to the
        *destination* mailbox.

        Args:
            uid: The UID of the message to copy.
            destination: The destination mailbox.
            recent: True if the message should be marked recent.

        """
        ...

    @abstractmethod
    async def move(self: MailboxDataT, uid: int, destination: MailboxDataT, *,
                   recent: bool = False) -> Optional[int]:
        """Moves a message, if it exists, from this mailbox to the
        *destination* mailbox.

        Args:
            uid: The UID of the message to move.
            destination: The destination mailbox.
            recent: True if the message should be marked recent.

        """
        ...

    @abstractmethod
    async def get(self, uid: int, cached_msg: CachedMessage) -> MessageT_co:
        """Return the message with the given UID.

        Args:
            uid: The message UID.
            cached_msg: The last known cached message.

        """
        ...

    @abstractmethod
    async def update(self, uid: int, cached_msg: CachedMessage,
                     flag_set: frozenset[Flag], mode: FlagOp) -> MessageT_co:
        """Update the permanent flags of the message.

        Args:
            uid: The message UID.
            cached_msg: The last known cached message.
            flag_set: The set of flags for the update operation.
            flag_op: The mode to change the flags.

        """
        ...

    @abstractmethod
    async def delete(self, uids: Iterable[int]) -> None:
        """Delete messages with the given UIDs.

        Args:
            uids: The message UIDs.

        """
        ...

    @abstractmethod
    async def claim_recent(self, selected: SelectedMailbox) -> None:
        """Messages that are newly added to the mailbox are assigned the
        ``\\Recent`` flag in the current selected mailbox session.

        Args:
            selected: The selected mailbox session.

        """
        ...

    @abstractmethod
    async def cleanup(self) -> None:
        """Perform any necessary "housekeeping" steps. This may be a slow
        operation, and may run things like garbage collection on the backend.

        See Also:
            :meth:`~pymap.interfaces.session.SessionInterface.check_mailbox`

        """
        ...

    @abstractmethod
    async def snapshot(self) -> MailboxSnapshot:
        """Returns a snapshot of the current state of the mailbox."""
        ...

    async def find(self, seq_set: SequenceSet, selected: SelectedMailbox) \
            -> AsyncIterable[tuple[int, MessageT_co]]:
        """Find the active message UID and message pairs in the mailbox that
        are contained in the given sequences set. Message sequence numbers
        are resolved by the selected mailbox session.

        Args:
            seq_set: The sequence set of the desired messages.
            selected: The selected mailbox session.

        """
        for seq, cached_msg in selected.messages.get_all(seq_set):
            msg = await self.get(cached_msg.uid, cached_msg)
            if msg is not None:
                yield (seq, msg)

    async def find_deleted(self, seq_set: SequenceSet,
                           selected: SelectedMailbox) -> Sequence[int]:
        """Return all the active message UIDs that have the ``\\Deleted`` flag.

        Args:
            seq_set: The sequence set of the possible messages.
            selected: The selected mailbox session.

        """
        session_flags = selected.session_flags
        return [msg.uid async for _, msg in self.find(seq_set, selected)
                if Deleted in msg.get_flags(session_flags)]


class MailboxSetInterface(Protocol[MailboxDataT_co]):
    """Manages the set of mailboxes available to the authenticated user."""

    @property
    @abstractmethod
    def delimiter(self) -> str:
        """The delimiter used in mailbox names to indicate hierarchy."""
        ...

    @abstractmethod
    async def set_subscribed(self, name: str, subscribed: bool) -> None:
        """Add or remove the subscribed status of a mailbox.

        See Also:
            :meth:`~pymap.interfaces.session.SessionInterface.subscribe`
            :meth:`~pymap.interfaces.session.SessionInterface.unsubscribe`

        Args:
            name: The name of the mailbox.
            subscribed: True if the mailbox should be subscribed.

        """
        ...

    @abstractmethod
    async def list_subscribed(self) -> ListTree:
        """Return a list of all subscribed mailboxes.

        See Also:
            :meth:`~pymap.interfaces.session.SessionInterface.list_mailboxes`

        """
        ...

    @abstractmethod
    async def list_mailboxes(self) -> ListTree:
        """Return a list of all mailboxes.

        See Also:
            :meth:`~pymap.interfaces.session.SessionInterface.list_mailboxes`

        """
        ...

    @abstractmethod
    async def get_mailbox(self, name: str) -> MailboxDataT_co:
        """Return an existing mailbox by name.

        Args:
            name: The name of the mailbox.

        Raises:
            KeyError: The mailbox did not exist.

        """
        ...

    @abstractmethod
    async def add_mailbox(self, name: str) -> ObjectId:
        """Create a new mailbox, returning its object ID.

        See Also:
            :meth:`~pymap.interfaces.session.SessionInterface.create_mailbox`

        Args:
            name: The name of the mailbox.

        Raises:
            ValueError: The mailbox already exists.

        """
        ...

    @abstractmethod
    async def delete_mailbox(self, name: str) -> None:
        """Delete an existing mailbox.

        See Also:
            :meth:`~pymap.interfaces.session.SessionInterface.delete_mailbox`

        Args:
            name: The name of the mailbox.

        Raises:
            KeyError: The mailbox did not exist.

        """
        ...

    @abstractmethod
    async def rename_mailbox(self, before: str, after: str) -> None:
        """Rename an existing mailbox.

        See Also:
            :meth:`~pymap.interfaces.session.SessionInterface.rename_mailbox`

        Args:
            before: The name of the existing mailbox.
            after: The name of the destination mailbox.

        Raises:
            KeyError: The *before* mailbox does not exist.
            ValueError: The *after* mailbox already exists.

        """
        ...
