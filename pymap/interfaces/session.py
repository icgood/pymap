
from abc import abstractmethod
from typing import Any, Tuple, Optional, FrozenSet, Iterable, Sequence
from typing_extensions import Protocol

from pysasl import AuthenticationCredentials

from .filter import FilterSetInterface
from .message import AppendMessage, MessageInterface
from .mailbox import MailboxInterface
from ..concurrent import Event
from ..config import ConfigT_contra
from ..flags import FlagOp
from ..parsing.specials import SequenceSet, Flag, SearchKey, ObjectId
from ..parsing.response.code import AppendUid, CopyUid
from ..selected import SelectedMailbox

__all__ = ['LoginProtocol', 'SessionInterface']


class LoginProtocol(Protocol[ConfigT_contra]):
    """Defines the callback protocol that backends use to initialize a new
    session.

    """

    async def __call__(self, credentials: AuthenticationCredentials,
                       config: ConfigT_contra) -> 'SessionInterface':
        """Given a set of authentication credentials, initialize and return a
        new IMAP session for the user.

        Args:
            credentials: Authentication credentials supplied by the user.
            config: The config in use by the server.

        Raises:
            :class:`~pymap.exceptions.InvalidAuth`

        """
        ...


class SessionInterface(Protocol):
    """Corresponds to a single, authenticated IMAP session."""

    @property
    @abstractmethod
    def owner(self) -> str:
        """The SASL authorization identity of the logged-in user."""
        ...

    @property
    @abstractmethod
    def filter_set(self) -> Optional[FilterSetInterface[Any]]:
        """Manages the active and inactive filters for the login user."""
        ...

    @abstractmethod
    async def cleanup(self) -> None:
        """Called after ever operation, success or failure, to allow the
        backend to clean up resources.

        Note:
            Any exception raised by this method will be silently ignored.

        """
        ...

    @abstractmethod
    async def list_mailboxes(self, ref_name: str, filter_: str,
                             subscribed: bool = False,
                             selected: SelectedMailbox = None) \
            -> Tuple[Iterable[Tuple[str, Optional[str], Sequence[bytes]]],
                     Optional[SelectedMailbox]]:
        """List the mailboxes owned by the user.

        See Also:
            `RFC 3501 6.3.8.
            <https://tools.ietf.org/html/rfc3501#section-6.3.8>`_,
            `RFC 3501 6.3.9.
            <https://tools.ietf.org/html/rfc3501#section-6.3.9>`_

        Args:
            ref_name: Mailbox reference name.
            filter_: Mailbox name with possible wildcards.
            subscribed: If True, only list the subscribed mailboxes.
            selected: If applicable, the currently selected mailbox name.

        """
        ...

    @abstractmethod
    async def get_mailbox(self, name: str, selected: SelectedMailbox = None) \
            -> Tuple[MailboxInterface, Optional[SelectedMailbox]]:
        """Retrieves a :class:`~pymap.interfaces.mailbox.MailboxInterface`
        object corresponding to an existing mailbox owned by the user. Raises
        an exception if the mailbox does not yet exist.

        Args:
            name: The name of the mailbox.
            selected: If applicable, the currently selected mailbox name.

        Raises:
            :class:`~pymap.exceptions.MailboxNotFound`

        """
        ...

    @abstractmethod
    async def create_mailbox(self, name: str,
                             selected: SelectedMailbox = None) \
            -> Tuple[ObjectId, Optional[SelectedMailbox]]:
        """Creates a new mailbox owned by the user.

        See Also:
            `RFC 3501 6.3.3.
            <https://tools.ietf.org/html/rfc3501#section-6.3.3>`_

        Args:
            name: The name of the mailbox.
            selected: If applicable, the currently selected mailbox name.

        Raises:
            :class:`~pymap.exceptions.MailboxConflict`

        """
        ...

    @abstractmethod
    async def delete_mailbox(self, name: str,
                             selected: SelectedMailbox = None) \
            -> Optional[SelectedMailbox]:
        """Deletes the mailbox owned by the user.

        See Also:
            `RFC 3501 6.3.4.
            <https://tools.ietf.org/html/rfc3501#section-6.3.4>`_

        Args:
            name: The name of the mailbox.
            selected: If applicable, the currently selected mailbox name.

        Raises:
            :class:`~pymap.exceptions.MailboxNotFound`
            :class:`~pymap.exceptions.MailboxHasChildren`

        """
        ...

    @abstractmethod
    async def rename_mailbox(self, before_name: str, after_name: str,
                             selected: SelectedMailbox = None) \
            -> Optional[SelectedMailbox]:
        """Renames the mailbox owned by the user.

        See Also:
            `RFC 3501 6.3.5.
            <https://tools.ietf.org/html/rfc3501#section-6.3.5>`_

        Args:
            before_name: The name of the mailbox before the rename.
            after_name: The name of the mailbox after the rename.
            selected: If applicable, the currently selected mailbox name.

        Raises:
            :class:`~pymap.exceptions.MailboxNotFound`
            :class:`~pymap.exceptions.MailboxConflict`

        """
        ...

    @abstractmethod
    async def subscribe(self, name: str, selected: SelectedMailbox = None) \
            -> Optional[SelectedMailbox]:
        """Mark the given folder name as subscribed, whether or not the given
        folder name currently exists.

        See Also:
            `RFC 3501 6.3.6.
            <https://tools.ietf.org/html/rfc3501#section-6.3.6>`_

        Args:
            name: The name of the mailbox.
            selected: If applicable, the currently selected mailbox name.

        Raises:
            :class:`~pymap.exceptions.MailboxNotFound`

        """
        ...

    @abstractmethod
    async def unsubscribe(self, name: str, selected: SelectedMailbox = None) \
            -> Optional[SelectedMailbox]:
        """Remove the given folder name from the subscription list, whether or
        not the given folder name currently exists.

        See Also:
            `RFC 3501 6.3.6.
            <https://tools.ietf.org/html/rfc3501#section-6.3.6>`_

        Args:
            name: The name of the mailbox.
            selected: If applicable, the currently selected mailbox name.

        Raises:
            :class:`~pymap.exceptions.MailboxNotFound`

        """
        ...

    @abstractmethod
    async def append_messages(self, name: str,
                              messages: Sequence[AppendMessage],
                              selected: SelectedMailbox = None) \
            -> Tuple[AppendUid, Optional[SelectedMailbox]]:
        """Appends a message to the end of the mailbox.

        See Also:
            `RFC 3502 6.3.11.
            <https://tools.ietf.org/html/rfc3502#section-6.3.11>`_

        Args:
            name: The name of the mailbox.
            messages: The messages to append.
            selected: If applicable, the currently selected mailbox name.

        Raises:
            :class:`~pymap.exceptions.MailboxNotFound`
            :class:`~pymap.exceptions.AppendFailure`

        """
        ...

    @abstractmethod
    async def select_mailbox(self, name: str, readonly: bool = False) \
            -> Tuple[MailboxInterface, SelectedMailbox]:
        """Selects an existing mailbox owned by the user. The returned session
        is then used as the ``selected`` argument to other methods to fetch
        mailbox updates.

        See Also:
            `RFC 3501 6.3.1.
            <https://tools.ietf.org/html/rfc3501#section-6.3.1>`_,
            `RFC 3501 6.3.2.
            <https://tools.ietf.org/html/rfc3501#section-6.3.2>`_

        Args:
            name: The name of the mailbox.
            readonly: True if the mailbox is read-only.

        Raises:
            :class:`~pymap.exceptions.MailboxNotFound`

        """
        ...

    @abstractmethod
    async def check_mailbox(self, selected: SelectedMailbox, *,
                            wait_on: Event = None,
                            housekeeping: bool = False) -> SelectedMailbox:
        """Checks for any updates in the mailbox.

        If ``wait_on`` is given, this method should block until either this
        event is signalled or the mailbox has detected updates. This method may
        be called continuously as long as ``wait_on`` is not signalled.

        If ``housekeeping`` is True, perform any house-keeping necessary by the
        mailbox backend, which may be a slower operation.

        See Also:
            `RFC 3501 6.1.2.
            <https://tools.ietf.org/html/rfc3501#section-6.1.2>`_,
            `RFC 3501 6.4.1.
            <https://tools.ietf.org/html/rfc3501#section-6.4.1>`_
            `RFC 2177 <https://tools.ietf.org/html/rfc2177>`_

        Args:
            selected: The selected mailbox session.
            wait_on: If given, block until this event signals.
            housekeeping: If True, the backend may perform additional
                housekeeping operations if necessary.

        Raises:
            :class:`~pymap.exceptions.MailboxNotFound`

        """
        ...

    @abstractmethod
    async def fetch_messages(self, selected: SelectedMailbox,
                             sequence_set: SequenceSet,
                             set_seen: bool) \
            -> Tuple[Iterable[Tuple[int, MessageInterface]], SelectedMailbox]:
        """Get a list of loaded message objects corresponding to given sequence
        set.

        Args:
            selected: The selected mailbox session.
            sequence_set: Sequence set of message sequences or UIDs.
            set_seen: True if the messages should get the ``\\Seen`` flag.

        Raises:
            :class:`~pymap.exceptions.MailboxNotFound`

        """
        ...

    @abstractmethod
    async def search_mailbox(self, selected: SelectedMailbox,
                             keys: FrozenSet[SearchKey]) \
            -> Tuple[Iterable[Tuple[int, MessageInterface]], SelectedMailbox]:
        """Get the messages in the current mailbox that meet all of the
        given search criteria.

        See Also:
            `RFC 3501 7.2.5.
            <https://tools.ietf.org/html/rfc3501#section-7.2.5>`_

        Args:
            selected: The selected mailbox session.
            keys: Search keys specifying the message criteria.

        Raises:
            :class:`~pymap.exceptions.MailboxNotFound`

        """
        ...

    @abstractmethod
    async def expunge_mailbox(self, selected: SelectedMailbox,
                              uid_set: SequenceSet = None) -> SelectedMailbox:
        """All messages that are marked as deleted are immediately expunged
        from the mailbox.

        See Also:
            `RFC 3501 6.4.3.
            <https://tools.ietf.org/html/rfc3501#section-6.4.3>`_
            `RFC 4315 2.1 <https://tools.ietf.org/html/rfc4315#section-2.1>`_

        Args:
            selected: The selected mailbox session.
            uid_set: Only the messages in the given UID set should be expunged.

        Raises:
            :class:`~pymap.exceptions.MailboxNotFound`
            :class:`~pymap.exceptions.MailboxReadOnly`

        """
        ...

    @abstractmethod
    async def copy_messages(self, selected: SelectedMailbox,
                            sequence_set: SequenceSet,
                            mailbox: str) \
            -> Tuple[Optional[CopyUid], SelectedMailbox]:
        """Copy a set of messages into the given mailbox.

        See Also:
            `RFC 3501 6.4.7.
            <https://tools.ietf.org/html/rfc3501#section-6.4.7>`_

        Args:
            selected: The selected mailbox session.
            sequence_set: Sequence set of message sequences or UIDs.
            mailbox: Name of the mailbox to copy messages into.

        Raises:
            :class:`~pymap.exceptions.MailboxNotFound`
            :class:`~pymap.exceptions.MailboxReadOnly`

        """
        ...

    @abstractmethod
    async def update_flags(self, selected: SelectedMailbox,
                           sequence_set: SequenceSet,
                           flag_set: FrozenSet[Flag],
                           mode: FlagOp = FlagOp.REPLACE) \
            -> Tuple[Iterable[Tuple[int, MessageInterface]], SelectedMailbox]:
        """Update the flags for the given set of messages.

        See Also:
            `RFC 3501 6.4.6.
            <https://tools.ietf.org/html/rfc3501#section-6.4.6>`_

        Args:
            selected: The selected mailbox session.
            sequence_set: Sequence set of message sequences or UIDs.
            flag_set: Set of flags to update.
            mode: Update mode for the flag set.

        Raises:
            :class:`~pymap.exceptions.MailboxNotFound`
            :class:`~pymap.exceptions.MailboxReadOnly`

        """
        ...
