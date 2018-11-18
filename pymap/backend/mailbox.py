
from abc import abstractmethod
from typing import TypeVar, Optional, Tuple, Sequence, FrozenSet, AsyncIterable
from typing_extensions import Protocol

from pymap.mailbox import MailboxSnapshot
from pymap.message import AppendMessage, BaseMessage, BaseLoadedMessage
from pymap.parsing.specials import SequenceSet
from pymap.parsing.specials.flag import get_system_flags, Flag, Recent, Seen
from pymap.selected import SelectedSet, SelectedMailbox

from .util import asyncenumerate

__all__ = ['MailboxDataInterface', 'MailboxSetInterface',
           'Message', 'LoadedMessage']

_MessageT = TypeVar('_MessageT', bound='Message', contravariant=True)
_LoadedT = TypeVar('_LoadedT', bound='LoadedMessage')
_DataT = TypeVar('_DataT', bound='MailboxDataInterface', covariant=True)


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


class LoadedMessage(BaseLoadedMessage, Message):
    """Manages a single message. This message has had its contents loaded
    into memory and parsed into a MIME representation.

    """
    pass


class MailboxDataInterface(Protocol[_MessageT, _LoadedT]):
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
    @abstractmethod
    def next_uid(self) -> int:
        """The predicted next message UID."""
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
    def parse_message(self, append_msg: AppendMessage) -> _LoadedT:
        """Parse the raw message data into a loaded message object.

        Args:
            append_msg: A single message from the APPEND command.

        """
        ...

    @abstractmethod
    async def add(self, message: _LoadedT, recent: bool = False) -> _LoadedT:
        """Adds a new message to the end of the mailbox, returning a copy of
        message with its assigned UID.

        Args:
            message: The loaded message object.
            recent: True if the message should be marked recent.

        """
        ...

    @abstractmethod
    async def get(self, uid: int) -> Optional[_LoadedT]:
        """Return the message with the given UID, if it exists.

        Args:
            uid: The message UID.

        """
        ...

    @abstractmethod
    async def delete(self, uid: int) -> None:
        """Delete the message with the given UID, if it exists.

        Args:
            uid: The message UID.

        """
        ...

    @abstractmethod
    async def save_flags(self, *messages: _MessageT) -> None:
        """Save the flags currently stored in each message's
        :attr:`~pymap.interfaces.message.Message.permanent_flags` set.

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
    def messages(self) -> AsyncIterable[_LoadedT]:
        """Return all of the active messages in the mailbox."""
        ...

    @abstractmethod
    def items(self) -> AsyncIterable[Tuple[int, _LoadedT]]:
        """Return all of the active message UID and message pairs in the
        mailbox.

        """
        ...

    async def find(self, seq_set: SequenceSet, selected: SelectedMailbox) \
            -> AsyncIterable[Tuple[int, _LoadedT]]:
        """Find the active message UID and message pairs in the mailbox that
        are contained in the given sequences set. Message sequence numbers
        are resolved by the selected mailbox session.

        Args:
            seq_set: The sequence set of the desired messages.
            selected: The selected mailbox session.

        """
        for seq, uid in selected.snapshot.iter_set(seq_set):
            msg = await self.get(uid)
            if msg is not None:
                yield (seq, msg)

    async def snapshot(self) -> MailboxSnapshot:
        """Returns a snapshot of the current state of the mailbox."""
        exists = 0
        recent = 0
        unseen = 0
        first_unseen: Optional[int] = None
        async for seq, msg in asyncenumerate(self.messages(), 1):
            exists += 1
            if msg.recent:
                recent += 1
            if Seen not in msg.permanent_flags:
                unseen += 1
                if first_unseen is None:
                    first_unseen = seq
        return MailboxSnapshot(self.name, self.readonly, self.uid_validity,
                               self.permanent_flags, self.session_flags,
                               exists, recent, unseen, first_unseen,
                               self.next_uid)


class MailboxSetInterface(Protocol[_DataT]):
    """Manages the set of mailboxes available to the authenticated user."""

    @property
    @abstractmethod
    def inbox(self) -> _DataT:
        """The INBOX mailbox, which must always exist."""
        ...

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
    async def get_mailbox(self, name: str, try_create: bool = False) -> _DataT:
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
    async def add_mailbox(self, name: str) -> _DataT:
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
    async def rename_mailbox(self, before: str, after: str) -> _DataT:
        """Rename an existing mailbox.

        See Also:
            :meth:`~pymap.interfaces.session.SessionInterface.rename_mailbox`

        Args:
            before: The name of the existing mailbox.
            after: The name of the destination mailbox.

        Raises:

        """
        ...
