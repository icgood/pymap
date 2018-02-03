# Copyright (c) 2014 Ian C. Good
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#

"""Module defining the interfaces available to pymap backends."""

from datetime import datetime
from typing import Tuple, Optional, AbstractSet, FrozenSet, Any, Dict, Iterable

from .parsing.response import Response
from .flag import FlagOp
from .parsing.specials import SequenceSet, FetchAttribute, Flag, SearchKey
from .structure import MessageStructure, UpdateType

__all__ = ['MailboxInterface', 'SessionInterface']


class MailboxInterface:
    """Corresponds to a mailbox state on an IMAP session, since the last
    update from the backend.

    """

    def get_flags(self, message: MessageStructure) -> FrozenSet[Flag]:
        """Get the full set of permanent and session flags.

        :param message: The message to get flags for.

        """
        raise NotImplementedError

    def update_flags(self, message: MessageStructure,
                     flag_set: AbstractSet[Flag],
                     flag_op: FlagOp = FlagOp.REPLACE) -> None:
        """Update the flags on a message in the mailbox. After this call,
        the ``message.permanent_flags`` set should be persisted by the
        backend.

        :param message: The message to set flags on.
        :param flag_set: The set of flags for the update operation.
        :param flag_op: fThe

        """
        raise NotImplementedError

    def get_updates(self, before: 'MailboxInterface') -> Iterable[Response]:
        """Compare the current state to a previous state and return the
        update responses.

        :param before: The previous state of the mailbox.
        :return: Untagged responses to prepend.

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
        """The permanent flags allowed in the mailbox."""
        raise NotImplementedError

    @property
    def updates(self) -> Dict[int, Tuple[UpdateType, MessageStructure]]:
        raise NotImplementedError

    @property
    def mailbox_session(self) -> Any:
        """Hashable value used to key the session flags in the mailbox."""
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
    def first_unseen(self) -> int:
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


class SessionInterface:
    """Corresponds to a single, authenticated IMAP session."""

    async def list_mailboxes(self, ref_name: str,
                             filter_: str,
                             subscribed: bool = False,
                             selected: Optional[MailboxInterface] = None) \
            -> Tuple[Iterable[Tuple[str, bytes, Dict[str, bool]]],
                     Optional[MailboxInterface]]:
        """List the mailboxes owned by the user.

        .. seealso:: `RFC 3501 6.3.8
        <https://tools.ietf.org/html/rfc3501#section-6.3.8>`_, `RFC 3501
        6.3.9 <https://tools.ietf.org/html/rfc3501#section-6.3.9>`_

        :param ref_name: Mailbox reference name.
        :param filter_: Mailbox name with possible wildcards.
        :param subscribed: If true, only list the subscribed mailboxes.
        :param selected: If applicable, the currently selected mailbox name.

        """
        raise NotImplementedError

    async def get_mailbox(self, name: str,
                          claim_recent: bool = False,
                          selected: Optional[MailboxInterface] = None) \
            -> Tuple[MailboxInterface, Optional[MailboxInterface]]:
        """Retrieves a :class:`MailboxInterface` object corresponding to an
        existing mailbox owned by the user. Raises an exception if the
        mailbox does not yet exist.

        :param name: The name of the mailbox.
        :param claim_recent: If True, the session should claim any pending
                             ``\Recent`` flags in the mailbox.
        :param selected: If applicable, the currently selected mailbox name.
        :raises pymap.exceptions.MailboxNotFound:

        """
        raise NotImplementedError

    async def create_mailbox(self, name: str,
                             selected: Optional[MailboxInterface] = None) \
            -> Optional[MailboxInterface]:
        """Creates a new mailbox owned by the user.

        .. seealso:: `RFC 3501 6.3.3
        <https://tools.ietf.org/html/rfc3501#section-6.3.3>`_

        :param name: The name of the mailbox.
        :param selected: If applicable, the currently selected mailbox name.
        :raises pymap.exceptions.MailboxConflict:

        """
        raise NotImplementedError

    async def delete_mailbox(self, name: str,
                             selected: Optional[MailboxInterface] = None) \
            -> Optional[MailboxInterface]:
        """Deletes the mailbox owned by the user.

        .. seealso:: `RFC 3501 6.3.4
        <https://tools.ietf.org/html/rfc3501#section-6.3.4>`_

        :param name: The name of the mailbox.
        :param selected: If applicable, the currently selected mailbox name.
        :raises pymap.exceptions.MailboxNotFound:
        :raises pymap.exceptions.MailboxHasChildren:

        """
        raise NotImplementedError

    async def rename_mailbox(self, before_name: str, after_name: str,
                             selected: Optional[MailboxInterface] = None) \
            -> Optional[MailboxInterface]:
        """Renames the mailbox owned by the user.

        .. seealso:: `RFC 3501 6.3.5
        <https://tools.ietf.org/html/rfc3501#section-6.3.5>`_

        :param before_name: The name of the mailbox before the rename.
        :param after_name: The name of the mailbox after the rename.
        :param selected: If applicable, the currently selected mailbox name.
        :raises pymap.exceptions.MailboxNotFound:
        :raises pymap.exceptions.MailboxConflict:

        """
        raise NotImplementedError

    async def subscribe(self, name: str,
                        selected: Optional[MailboxInterface] = None) \
            -> Optional[MailboxInterface]:
        """Mark the given folder name as subscribed, whether or not the given
        folder name currently exists.

        .. seealso:: `RFC 3501 6.3.6
        <https://tools.ietf.org/html/rfc3501#section-6.3.6>`_

        :param name: The name of the mailbox.
        :param selected: If applicable, the currently selected mailbox name.

        """
        raise NotImplementedError

    async def unsubscribe(self, name: str,
                          selected: Optional[MailboxInterface] = None) \
            -> Optional[MailboxInterface]:
        """Remove the given folder name from the subscription list, whether or
        not the given folder name currently exists.

        .. seealso:: `RFC 3501 6.3.6
        <https://tools.ietf.org/html/rfc3501#section-6.3.6>`_

        :param name: The name of the mailbox.
        :param selected: If applicable, the currently selected mailbox name.

        """
        raise NotImplementedError

    async def append_message(self, name: str,
                             message: bytes,
                             flag_set: AbstractSet[bytes],
                             when: Optional[datetime] = None,
                             selected: Optional[MailboxInterface] = None) \
            -> Optional[MailboxInterface]:
        """Appends a message to the end of the mailbox.

        .. seealso:: `RFC 3501 6.3.11
        <https://tools.ietf.org/html/rfc3501#section-6.3.11>`_

        :param name: The name of the mailbox.
        :param message: The contents of the message.
        :param flag_set: Set of flag bytestrings.
        :param when: The internal time associated with the message.
        :param selected: If applicable, the currently selected mailbox name.
        :raises pymap.exceptions.MailboxNotFound:
        :raises pymap.exceptions.AppendFailure:

        """
        raise NotImplementedError

    async def check_mailbox(self, selected: MailboxInterface,
                            housekeeping: bool = False) \
            -> Optional[MailboxInterface]:
        """Checks for any updates in the mailbox. Optionally performs any
        house-keeping necessary by the mailbox backend, which may be a
        slower operation.

        :param selected: The name of the selected mailbox.
        :param housekeeping: If True, the backend may perform additional
                             housekeeping operations if necessary.

        .. seealso:: `RFC 3501 6.1.2
        <https://tools.ietf.org/html/rfc3501#section-6.1.2>`_, `RFC 3501 6.4.1
        <https://tools.ietf.org/html/rfc3501#section-6.4.1>`_

        """
        raise NotImplementedError

    async def fetch_messages(self, selected: MailboxInterface,
                             sequences: SequenceSet,
                             attributes: AbstractSet[FetchAttribute]) \
            -> Tuple[Iterable[Tuple[int, MessageStructure]],
                     Optional[MailboxInterface]]:
        """Get a list of :class:`MessageStructure` objects corresponding to
        given sequence set.

        :param selected: The name of the selected mailbox.
        :param sequences: Sequence set of message sequences or UIDs.
        :param attributes: Fetch attributes for the messages.

        """
        raise NotImplementedError

    async def search_mailbox(self, selected: MailboxInterface,
                             keys: FrozenSet[SearchKey]) \
            -> Tuple[Iterable[int], Optional[MailboxInterface]]:
        """Get the :class:`MessageInterface` objects in the current mailbox
        that meet the given search criteria.

        .. seealso:: `RFC 3501 7.2.5
        <https://tools.ietf.org/html/rfc3501#section-7.2.5>`_

        :param selected: The name of the selected mailbox.
        :param keys: Search keys specifying the message criteria.

        """
        raise NotImplementedError

    async def expunge_mailbox(self, selected: MailboxInterface) \
            -> Tuple[Iterable[int], Optional[MailboxInterface]]:
        """All messages that are marked as deleted are immediately expunged
        from the mailbox.

        .. seealso:: `RFC 3501 6.4.3
        <https://tools.ietf.org/html/rfc3501#section-6.4.3>`_

        :param selected: The name of the selected mailbox.
        :raises pymap.exceptions.MailboxReadOnly:

        """
        raise NotImplementedError

    async def copy_messages(self, selected: MailboxInterface,
                            sequences: SequenceSet,
                            mailbox: str) \
            -> Optional[MailboxInterface]:
        """Copy a set of messages into the given mailbox.

        .. seealso:: `RFC 3501 6.4.7
        <https://tools.ietf.org/html/rfc3501#section-6.4.7>`_

        :param selected: The name of the selected mailbox.
        :param sequences: Sequence set of message sequences or UIDs.
        :param mailbox: Name of the mailbox to copy messages into.
        :raises pymap.exceptions.MailboxNotFound:

        """
        raise NotImplementedError

    async def update_flags(self, selected: MailboxInterface,
                           sequences: SequenceSet,
                           flag_set: AbstractSet[Flag],
                           mode: FlagOp = FlagOp.REPLACE) \
            -> Tuple[Iterable[Tuple[int, MessageStructure]],
                     Optional[MailboxInterface]]:
        """Update the flags for the given set of messages.

        .. seealso:: `RFC 3501 6.4.6
        <https://tools.ietf.org/html/rfc3501#section-6.4.6>`_

        :param selected: The name of the selected mailbox.
        :param sequences: Sequence set of message sequences or UIDs.
        :param flag_set: Set of flags to update.
        :param mode: Update mode for the flag set.

        """
        raise NotImplementedError
