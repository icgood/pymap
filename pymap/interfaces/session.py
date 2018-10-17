from datetime import datetime
from typing import Tuple, Optional, FrozenSet, Dict, Iterable

from pysasl import AuthenticationCredentials

from .message import Message, LoadedMessage
from .mailbox import MailboxInterface
from ..flags import FlagOp
from ..parsing.specials import SequenceSet, FetchAttribute, Flag, SearchKey
from ..selected import SelectedMailbox

__all__ = ['SessionInterface']


class SessionInterface:
    """Corresponds to a single, authenticated IMAP session."""

    async def list_mailboxes(self, ref_name: str,
                             filter_: str,
                             subscribed: bool = False,
                             selected: SelectedMailbox = None) \
            -> Tuple[Iterable[Tuple[str, bytes, Dict[str, bool]]],
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
        raise NotImplementedError

    async def get_mailbox(self, name: str,
                          selected: SelectedMailbox = None) \
            -> Tuple[MailboxInterface, Optional[SelectedMailbox]]:
        """Retrieves a :class:`'MailboxInterface'` object corresponding to an
        existing mailbox owned by the user. Raises an exception if the
        mailbox does not yet exist.

        Args:
            name: The name of the mailbox.
            selected: If applicable, the currently selected mailbox name.

        Raises:
            MailboxNotFound: The mailbox name does not exist.

        """
        raise NotImplementedError

    async def create_mailbox(self, name: str,
                             selected: SelectedMailbox = None) \
            -> Optional[SelectedMailbox]:
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
        raise NotImplementedError

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
            MailboxNotFound: The mailbox name does not exist.
            MailboxHasChildren: The mailbox has child mailboxes.

        """
        raise NotImplementedError

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
            MailboxNotFound: The mailbox name does not exist.
            MailboxConflict: The destination mailbox name already exists.

        """
        raise NotImplementedError

    async def subscribe(self, name: str,
                        selected: SelectedMailbox = None) \
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
            MailboxNotFound: The mailbox name does not exist.

        """
        raise NotImplementedError

    async def unsubscribe(self, name: str,
                          selected: SelectedMailbox = None) \
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
            MailboxNotFound: The mailbox name does not exist.

        """
        raise NotImplementedError

    async def append_message(self, name: str,
                             message: bytes,
                             flag_set: FrozenSet[Flag],
                             when: Optional[datetime] = None,
                             selected: SelectedMailbox = None) \
            -> Optional[SelectedMailbox]:
        """Appends a message to the end of the mailbox.

        See Also:
            `RFC 3501 6.3.11.
            <https://tools.ietf.org/html/rfc3501#section-6.3.11>`_

        Args:
            name: The name of the mailbox.
            message: The contents of the message.
            flag_set: Set of flag bytestrings.
            when: The internal time associated with the message.
            selected: If applicable, the currently selected mailbox name.

        Raises:
            MailboxNotFound: The mailbox name does not exist.
            AppendFailure: The message could not be appended to the mailbox.

        """
        raise NotImplementedError

    async def select_mailbox(self, name: str, readonly: bool = False) \
            -> Tuple['MailboxInterface', SelectedMailbox]:
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
        raise NotImplementedError

    async def check_mailbox(self, selected: SelectedMailbox,
                            housekeeping: bool = False) -> SelectedMailbox:
        """Checks for any updates in the mailbox. Optionally performs any
        house-keeping necessary by the mailbox backend, which may be a
        slower operation.

        See Also:
            `RFC 3501 6.1.2.
            <https://tools.ietf.org/html/rfc3501#section-6.1.2>`_,
            `RFC 3501 6.4.1.
            <https://tools.ietf.org/html/rfc3501#section-6.4.1>`_

        Args:
            selected: The selected mailbox session.
            housekeeping: If True, the backend may perform additional
                housekeeping operations if necessary.

        Raises:
            MailboxNotFound: The currently selected mailbox no longer exists.

        """
        raise NotImplementedError

    async def fetch_messages(self, selected: SelectedMailbox,
                             sequences: SequenceSet,
                             attributes: FrozenSet[FetchAttribute]) \
            -> Tuple[Iterable[Tuple[int, LoadedMessage]], SelectedMailbox]:
        """Get a list of :class:`LoadedMessage` objects corresponding to
        given sequence set.

        Args:
            selected: The selected mailbox session.
            sequences: Sequence set of message sequences or UIDs.
            attributes: Fetch attributes for the messages.

        Raises:
            MailboxNotFound: The currently selected mailbox no longer exists.

        """
        raise NotImplementedError

    async def search_mailbox(self, selected: SelectedMailbox,
                             keys: FrozenSet[SearchKey]) \
            -> Tuple[Iterable[Tuple[int, Message]], SelectedMailbox]:
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
        raise NotImplementedError

    async def expunge_mailbox(self, selected: SelectedMailbox) \
            -> SelectedMailbox:
        """All messages that are marked as deleted are immediately expunged
        from the mailbox.

        See Also:
            `RFC 3501 6.4.3.
            <https://tools.ietf.org/html/rfc3501#section-6.4.3>`_

        Args:
            selected: The selected mailbox session.

        Raises:
            MailboxNotFound: The currently selected mailbox no longer exists.
            MailboxReadOnly: The currently selected mailbox is read-only.

        """
        raise NotImplementedError

    async def copy_messages(self, selected: SelectedMailbox,
                            sequences: SequenceSet,
                            mailbox: str) -> SelectedMailbox:
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
        raise NotImplementedError

    async def update_flags(self, selected: SelectedMailbox,
                           sequences: SequenceSet,
                           flag_set: FrozenSet[Flag],
                           mode: FlagOp = FlagOp.REPLACE) \
            -> Tuple[Iterable[Tuple[int, Message]], SelectedMailbox]:
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
        raise NotImplementedError
