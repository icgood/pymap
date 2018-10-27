from abc import abstractmethod
from typing import Tuple, Optional, FrozenSet, Mapping, Iterable, Sequence, \
    TypeVar
from typing_extensions import Protocol

from pysasl import AuthenticationCredentials

from .message import Message, LoadedMessage
from .mailbox import MailboxInterface
from ..config import IMAPConfig
from ..flags import FlagOp
from ..message import AppendMessage
from ..parsing.specials import SequenceSet, FetchAttribute, Flag, SearchKey
from ..parsing.response.code import AppendUid, CopyUid
from ..selected import SelectedMailbox

__all__ = ['LoginProtocol', 'SessionInterface']

_Config = TypeVar('_Config', bound=IMAPConfig, contravariant=True)
_Selected = TypeVar('_Selected', bound=SelectedMailbox)


class LoginProtocol(Protocol[_Config, _Selected]):
    """Defines the callback protocol that backends use to initialize a new
    session.

    """

    async def __call__(self, credentials: AuthenticationCredentials,
                       config: _Config) -> 'SessionInterface[_Selected]':
        """Given a set of authentication credentials, initialize a new IMAP
        session for the user.

        Args:
            credentials: Authentication credentials supplied by the user.
            config: The config in use by the server.

        Returns:
            The new IMAP session.

        Raises:
            :class:`~pymap.exceptions.InvalidAuthentication`

        """
        ...


class SessionInterface(Protocol[_Selected]):
    """Corresponds to a single, authenticated IMAP session."""

    @abstractmethod
    async def list_mailboxes(self, ref_name: str,
                             filter_: str,
                             subscribed: bool = False,
                             selected: _Selected = None) \
            -> Tuple[Iterable[Tuple[str, bytes, Mapping[str, bool]]],
                     Optional[_Selected]]:
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
    async def get_mailbox(self, name: str, selected: _Selected = None) \
            -> Tuple[MailboxInterface, Optional[_Selected]]:
        """Retrieves a :class:`'MailboxInterface'` object corresponding to an
        existing mailbox owned by the user. Raises an exception if the
        mailbox does not yet exist.

        Args:
            name: The name of the mailbox.
            selected: If applicable, the currently selected mailbox name.

        Raises:
            MailboxNotFound: The mailbox name does not exist.

        """
        ...

    @abstractmethod
    async def create_mailbox(self, name: str, selected: _Selected = None) \
            -> Optional[_Selected]:
        """Creates a new mailbox owned by the user.

        See Also:
            `RFC 3501 6.3.3.
            <https://tools.ietf.org/html/rfc3501#section-6.3.3>`_

        Args:
            name: The name of the mailbox.
            selected: If applicable, the currently selected mailbox name.

        Raises:
            MailboxConflict: The mailbox name already exists.

        """
        ...

    @abstractmethod
    async def delete_mailbox(self, name: str, selected: _Selected = None) \
            -> Optional[_Selected]:
        """Deletes the mailbox owned by the user.

        See Also:
            `RFC 3501 6.3.4.
            <https://tools.ietf.org/html/rfc3501#section-6.3.4>`_

        Args:
            name: The name of the mailbox.
            selected: If applicable, the currently selected mailbox name.

        Raises:
            MailboxNotFound: The mailbox name does not exist.
            MailboxHasChildren: The mailbox has child mailboxes.

        """
        ...

    @abstractmethod
    async def rename_mailbox(self, before_name: str, after_name: str,
                             selected: _Selected = None) \
            -> Optional[_Selected]:
        """Renames the mailbox owned by the user.

        See Also:
            `RFC 3501 6.3.5.
            <https://tools.ietf.org/html/rfc3501#section-6.3.5>`_

        Args:
            before_name: The name of the mailbox before the rename.
            after_name: The name of the mailbox after the rename.
            selected: If applicable, the currently selected mailbox name.

        Raises:
            MailboxNotFound: The mailbox name does not exist.
            MailboxConflict: The destination mailbox name already exists.

        """
        ...

    @abstractmethod
    async def subscribe(self, name: str, selected: _Selected = None) \
            -> Optional[_Selected]:
        """Mark the given folder name as subscribed, whether or not the given
        folder name currently exists.

        See Also:
            `RFC 3501 6.3.6.
            <https://tools.ietf.org/html/rfc3501#section-6.3.6>`_

        Args:
            name: The name of the mailbox.
            selected: If applicable, the currently selected mailbox name.

        Raises:
            MailboxNotFound: The mailbox name does not exist.

        """
        ...

    @abstractmethod
    async def unsubscribe(self, name: str, selected: _Selected = None) \
            -> Optional[_Selected]:
        """Remove the given folder name from the subscription list, whether or
        not the given folder name currently exists.

        See Also:
            `RFC 3501 6.3.6.
            <https://tools.ietf.org/html/rfc3501#section-6.3.6>`_

        Args:
            name: The name of the mailbox.
            selected: If applicable, the currently selected mailbox name.

        Raises:
            MailboxNotFound: The mailbox name does not exist.

        """
        ...

    @abstractmethod
    async def append_messages(self, name: str,
                              messages: Sequence[AppendMessage],
                              selected: _Selected = None) \
            -> Tuple[AppendUid, Optional[_Selected]]:
        """Appends a message to the end of the mailbox.

        See Also:
            `RFC 3501 6.3.11.
            <https://tools.ietf.org/html/rfc3501#section-6.3.11>`_

        Args:
            name: The name of the mailbox.
            messages: The messages to append.
            selected: If applicable, the currently selected mailbox name.

        Raises:
            MailboxNotFound: The mailbox name does not exist.
            AppendFailure: The message could not be appended to the mailbox.

        """
        ...

    @abstractmethod
    async def select_mailbox(self, name: str, readonly: bool = False) \
            -> Tuple['MailboxInterface', _Selected]:
        """Selects a :class:`MailboxInterface` object corresponding to an
        existing mailbox owned by the user. The returned session is then
        used as the ``selected`` argument to other methods to fetch mailbox
        updates.

        See Also:
            `RFC 3501 6.3.1.
            <https://tools.ietf.org/html/rfc3501#section-6.3.1>`_,
            `RFC 3501 6.3.2.
            <https://tools.ietf.org/html/rfc3501#section-6.3.2>`_

        Args:
            name: The name of the mailbox.
            readonly: True if the mailbox is read-only.

        Raises:
            MailboxNotFound: The mailbox name does not exist.

        """
        ...

    @abstractmethod
    async def check_mailbox(self, selected: _Selected, block: bool = False,
                            housekeeping: bool = False) -> _Selected:
        """Checks for any updates in the mailbox.

        Optionally block until updates are available in the selected
        mailbox. Implementations may block however they want when ``block``
        is true.

        Optionally perform any house-keeping necessary by the mailbox
        backend, which may be a slower operation.

        See Also:
            `RFC 3501 6.1.2.
            <https://tools.ietf.org/html/rfc3501#section-6.1.2>`_,
            `RFC 3501 6.4.1.
            <https://tools.ietf.org/html/rfc3501#section-6.4.1>`_
            `RFC 2177 <https://tools.ietf.org/html/rfc2177>`_

        Args:
            selected: The selected mailbox session.
            block: If True, wait for updates to become available.
            housekeeping: If True, the backend may perform additional
                housekeeping operations if necessary.

        Raises:
            MailboxNotFound: The currently selected mailbox no longer exists.

        """
        ...

    @abstractmethod
    async def fetch_messages(self, selected: _Selected,
                             sequences: SequenceSet,
                             attributes: FrozenSet[FetchAttribute]) \
            -> Tuple[Iterable[Tuple[int, LoadedMessage]], _Selected]:
        """Get a list of :class:`LoadedMessage` objects corresponding to
        given sequence set.

        Args:
            selected: The selected mailbox session.
            sequences: Sequence set of message sequences or UIDs.
            attributes: Fetch attributes for the messages.

        Raises:
            MailboxNotFound: The currently selected mailbox no longer exists.

        """
        ...

    @abstractmethod
    async def search_mailbox(self, selected: _Selected,
                             keys: FrozenSet[SearchKey]) \
            -> Tuple[Iterable[Tuple[int, Message]], _Selected]:
        """Get the messages in the current mailbox that meet all of the
        given search criteria.

        See Also:
            `RFC 3501 7.2.5.
            <https://tools.ietf.org/html/rfc3501#section-7.2.5>`_

        Args:
            selected: The selected mailbox session.
            keys: Search keys specifying the message criteria.

        Raises:
            MailboxNotFound: The currently selected mailbox no longer exists.

        """
        ...

    @abstractmethod
    async def expunge_mailbox(self, selected: _Selected,
                              uid_set: SequenceSet = None) -> _Selected:
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
            MailboxNotFound: The currently selected mailbox no longer exists.
            MailboxReadOnly: The currently selected mailbox is read-only.

        """
        ...

    @abstractmethod
    async def copy_messages(self, selected: _Selected,
                            sequences: SequenceSet,
                            mailbox: str) \
            -> Tuple[Optional[CopyUid], _Selected]:
        """Copy a set of messages into the given mailbox.

        See Also:
            `RFC 3501 6.4.7.
            <https://tools.ietf.org/html/rfc3501#section-6.4.7>`_

        Args:
            selected: The selected mailbox session.
            sequences: Sequence set of message sequences or UIDs.
            mailbox: Name of the mailbox to copy messages into.

        Raises:
            MailboxNotFound: The currently selected mailbox no longer exists,
                or the destination mailbox does not exist.
            MailboxReadOnly: The currently selected mailbox is read-only,
                or the destination mailbox is read-only.

        """
        ...

    @abstractmethod
    async def update_flags(self, selected: _Selected,
                           sequences: SequenceSet,
                           flag_set: FrozenSet[Flag],
                           mode: FlagOp = FlagOp.REPLACE) \
            -> Tuple[Iterable[Tuple[int, Message]], _Selected]:
        """Update the flags for the given set of messages.

        See Also:
            `RFC 3501 6.4.6.
            <https://tools.ietf.org/html/rfc3501#section-6.4.6>`_

        Args:
            selected: The selected mailbox session.
            sequences: Sequence set of message sequences or UIDs.
            flag_set: Set of flags to update.
            mode: Update mode for the flag set.

        Raises:
            MailboxNotFound: The currently selected mailbox no longer exists.
            MailboxReadOnly: The currently selected mailbox is read-only.

        """
        ...
