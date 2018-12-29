
from abc import abstractmethod
from typing import TypeVar, Optional, Tuple, Sequence, FrozenSet, \
    Iterable, AsyncIterable
from typing_extensions import Protocol

from pymap.interfaces.message import AppendMessage, CachedMessage
from pymap.mailbox import MailboxSnapshot
from pymap.message import BaseMessage
from pymap.parsing.specials import SequenceSet, FetchRequirement
from pymap.parsing.specials.flag import get_system_flags, Flag, Recent, Seen
from pymap.selected import SelectedSet, SelectedMailbox

__all__ = ['MailboxDataInterface', 'MailboxSetInterface', 'Message',
           'MessageT', 'MailboxDataT', 'MailboxDataT_co']

#: Type variable with an upper bound of :class:`Message`.
MessageT = TypeVar('MessageT', bound='Message')

#: Type variable with an upper bound of :class:`MailboxDataInterface`.
MailboxDataT = TypeVar('MailboxDataT', bound='MailboxDataInterface')

#: Covariant type variable with an upper bound of
#: :class:`MailboxDataInterface`.
MailboxDataT_co = TypeVar('MailboxDataT_co', bound='MailboxDataInterface',
                          covariant=True)


class Message(BaseMessage):
    """Manages a single message. This message does not have its contents
    (headers, body, etc.) loaded into memory, it is only the IMAP metadata
    such as UID and flags.

    """

    @property
    def recent(self) -> bool:
        """True if the message is considered new in the mailbox. The next
        session to SELECT the mailbox will negate this value and apply the
        ``\\Recent`` session flag to the message.

        """
        return self._kwargs.get('recent', False)

    @recent.setter
    def recent(self, recent: bool) -> None:
        self._kwargs['recent'] = recent


class MailboxDataInterface(Protocol[MessageT]):
    """Manages the messages and metadata associated with a single mailbox."""

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
    def uid_validity(self) -> int:
        """The mailbox UID validity value."""
        ...

    @property
    def permanent_flags(self) -> FrozenSet[Flag]:
        """The permanent flags allowed in the mailbox."""
        return get_system_flags() - {Recent}

    @property
    def session_flags(self) -> FrozenSet[Flag]:
        """The session flags allowed in the mailbox."""
        return frozenset({Recent})

    @property
    @abstractmethod
    def selected_set(self) -> SelectedSet:
        """The set of selected mailbox sessions currently active."""
        ...

    @abstractmethod
    async def get_next_uid(self) -> int:
        """Return the predicted next message UID."""
        ...

    @abstractmethod
    async def update_selected(self, selected: SelectedMailbox) \
            -> SelectedMailbox:
        """Populates and returns the selected mailbox object with the state
        needed to discover updates.

        Args:
            selected: the selected mailbox object.

        """
        ...

    @abstractmethod
    async def add(self, message: AppendMessage, recent: bool = False) \
            -> MessageT:
        """Adds a new message to the end of the mailbox, returning a copy of
        message with its assigned UID.

        Args:
            message: The new message data.
            recent: True if the message should be marked recent.

        """
        ...

    @abstractmethod
    async def get(self, uid: int, cached_msg: CachedMessage = None,
                  requirement: FetchRequirement = FetchRequirement.METADATA) \
            -> Optional[MessageT]:
        """Return the message with the given UID.

        Args:
            uid: The message UID.
            cached_msg: The last known cached message.
            requirement: The data required from each message.

        Raises:
            IndexError: The UID is not valid in the mailbox.

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
    async def save_flags(self, messages: Iterable[MessageT]) -> None:
        """Save the permanent flags currently returned by each message's
        :attr:`~pymap.interfaces.message.Message.get_flags` method.

        Args:
            messages: The message objects.

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
    def uids(self) -> AsyncIterable[int]:
        """Return all of the active message UIDs in the mailbox."""
        ...

    @abstractmethod
    def messages(self) -> AsyncIterable[MessageT]:
        """Return all of the active messages in the mailbox."""
        ...

    @abstractmethod
    def items(self) -> AsyncIterable[Tuple[int, MessageT]]:
        """Return all of the active message UID and message pairs in the
        mailbox.

        """
        ...

    async def find(self, seq_set: SequenceSet, selected: SelectedMailbox,
                   requirement: FetchRequirement = FetchRequirement.METADATA) \
            -> AsyncIterable[Tuple[int, MessageT]]:
        """Find the active message UID and message pairs in the mailbox that
        are contained in the given sequences set. Message sequence numbers
        are resolved by the selected mailbox session.

        Args:
            seq_set: The sequence set of the desired messages.
            selected: The selected mailbox session.
            requirement: The data required from each message.

        """
        for seq, cached_msg in selected.messages.get_all(seq_set):
            msg = await self.get(cached_msg.uid, cached_msg, requirement)
            if msg is not None:
                yield (seq, msg)

    async def snapshot(self) -> MailboxSnapshot:
        """Returns a snapshot of the current state of the mailbox."""
        exists = 0
        recent = 0
        unseen = 0
        first_unseen: Optional[int] = None
        async for msg in self.messages():
            exists += 1
            if msg.recent:
                recent += 1
            if Seen not in msg.get_flags():
                unseen += 1
                if first_unseen is None:
                    first_unseen = exists
        return MailboxSnapshot(self.name, self.readonly, self.uid_validity,
                               self.permanent_flags, self.session_flags,
                               exists, recent, unseen, first_unseen,
                               await self.get_next_uid())


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
    async def list_subscribed(self) -> Sequence[str]:
        """Return a list of all subscribed mailboxes.

        See Also:
            :meth:`~pymap.interfaces.session.SessionInterface.list_mailboxes`

        """
        ...

    @abstractmethod
    async def list_mailboxes(self) -> Sequence[str]:
        """Return a list of all mailboxes.

        See Also:
            :meth:`~pymap.interfaces.session.SessionInterface.list_mailboxes`

        """
        ...

    @abstractmethod
    async def get_mailbox(self, name: str, try_create: bool = False) \
            -> MailboxDataT_co:
        """Return an existing mailbox.

        Args:
            name: The name of the mailbox.
            try_create: True if the operation might succeed if the mailbox
                is created first.

        Raises:
            :exc:`~pymap.exceptions.MailboxNotFound`

        """
        ...

    @abstractmethod
    async def add_mailbox(self, name: str) -> MailboxDataT_co:
        """Create a new mailbox.

        See Also:
            :meth:`~pymap.interfaces.session.SessionInterface.create_mailbox`

        Args:
            name: The name of the mailbox.

        Raises:
            :exc:`~pymap.exceptions.MailboxConflict`

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
            :exc:`~pymap.exceptions.MailboxNotFound`
            :exc:`~pymap.exceptions.MailboxHasChildren`

        """
        ...

    @abstractmethod
    async def rename_mailbox(self, before: str, after: str) -> MailboxDataT_co:
        """Rename an existing mailbox.

        See Also:
            :meth:`~pymap.interfaces.session.SessionInterface.rename_mailbox`

        Args:
            before: The name of the existing mailbox.
            after: The name of the destination mailbox.

        Raises:

        """
        ...
