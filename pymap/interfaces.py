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

import datetime
from typing import Tuple, Optional, AbstractSet, FrozenSet, Any, \
    Iterable, Dict, List as ListT

from pymap.parsing.response import Response
from pymap.parsing.response.specials import ExpungeResponse, FetchResponse, \
    ExistsResponse, RecentResponse
from .flag import FlagOp, Recent
from .parsing.primitives import List
from .parsing.specials import SequenceSet, FetchAttribute, Flag, SearchKey
from .structure import MessageStructure

__all__ = ['MailboxUpdates', 'MailboxState', 'SessionInterface']


class MailboxUpdates:

    def __init__(self):
        super().__init__()
        self._updates = {}

    @property
    def updates(self):
        return self._updates

    @property
    def exists(self) -> int:
        raise NotImplementedError

    @property
    def recent(self) -> int:
        raise NotImplementedError

    def add_expunge(self, *seqs: int):
        for seq in seqs:
            self.updates[seq] = ('expunge', None)

    def add_fetch(self, seq: int, msg: MessageStructure):
        self.updates[seq] = ('fetch', msg)

    def get_responses(self, before: 'MailboxState') -> Iterable[Response]:
        if before.exists != self.exists:
            yield ExistsResponse(self.exists)
        if before.recent != self.recent:
            yield RecentResponse(self.recent)
        all_updates = before.updates.copy()
        all_updates.update(self.updates)
        before.updates.clear()
        self.updates.clear()
        for seq in sorted(all_updates.keys()):
            update_type, msg = all_updates[seq]
            if update_type == 'expunge':
                yield ExpungeResponse(seq)
            elif update_type == 'fetch':
                data = {FetchAttribute(b'FLAGS'): List(msg.get_flags(self))}
                yield FetchResponse(seq, data)


class MailboxState(MailboxUpdates):
    """Corresponds to a mailbox available to the IMAP session."""

    def __init__(self, name: str,
                 permanent_flags: Optional[AbstractSet[Flag]] = None,
                 session_flags: Optional[AbstractSet[Flag]] = None,
                 readonly: bool = False,
                 uid_validity: int = 0):
        super().__init__()

        #: The name of the mailbox.
        self.name = name  # type: str

        if not permanent_flags:
            #: The permanent flags defined in the mailbox.
            self.permanent_flags = frozenset()  # type: FrozenSet[Flag]
        else:
            self.permanent_flags = frozenset(permanent_flags - {Recent})

        if not session_flags:
            #: The session flags defined in the mailbox.
            self.session_flags = frozenset({Recent})  # type: FrozenSet[Flag]
        else:
            self.session_flags = frozenset(
                (session_flags - self.permanent_flags) | {Recent}
            )

        #: If ``True``, the mailbox is read-only.
        self.readonly = readonly  # type: bool

        #: The UID validity value.
        self.uid_validity = uid_validity  # type: int

    @property
    def session(self) -> Any:
        """Hashable value used to key the session flags in the mailbox."""
        return self

    @property
    def flags(self) -> FrozenSet[Flag]:
        """Set of all permanent and session flags available on the mailbox."""
        return self.session_flags | self.permanent_flags

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


class SessionInterface:
    """Corresponds to a single, authenticated IMAP session."""

    async def list_mailboxes(self, ref_name: str,
                             filter_: str,
                             subscribed: bool = False,
                             selected: Optional[MailboxState] = None) \
            -> Tuple[ListT[Tuple[str, bytes, Dict[str, bool]]],
                     Optional[MailboxState]]:
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
                          selected: Optional[MailboxState] = None) \
            -> Tuple[MailboxState, Optional[MailboxState]]:
        """Retrieves a :class:`MailboxState` object corresponding to an
        existing mailbox owned by the user. Raises an exception if the
        mailbox does not yet exist.

        :param name: The name of the mailbox.
        :param selected: If applicable, the currently selected mailbox name.
        :raises pymap.exceptions.MailboxNotFound:

        """
        raise NotImplementedError

    async def create_mailbox(self, name: str,
                             selected: Optional[MailboxState] = None) \
            -> Optional[MailboxState]:
        """Creates a new mailbox owned by the user.

        .. seealso:: `RFC 3501 6.3.3
        <https://tools.ietf.org/html/rfc3501#section-6.3.3>`_

        :param name: The name of the mailbox.
        :param selected: If applicable, the currently selected mailbox name.
        :raises pymap.exceptions.MailboxConflict:

        """
        raise NotImplementedError

    async def delete_mailbox(self, name: str,
                             selected: Optional[MailboxState] = None) \
            -> Optional[MailboxState]:
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
                             selected: Optional[MailboxState] = None) \
            -> Optional[MailboxState]:
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
                        selected: Optional[MailboxState] = None) \
            -> Optional[MailboxState]:
        """Mark the given folder name as subscribed, whether or not the given
        folder name currently exists.

        .. seealso:: `RFC 3501 6.3.6
        <https://tools.ietf.org/html/rfc3501#section-6.3.6>`_

        :param name: The name of the mailbox.
        :param selected: If applicable, the currently selected mailbox name.

        """
        raise NotImplementedError

    async def unsubscribe(self, name: str,
                          selected: Optional[MailboxState] = None) \
            -> Optional[MailboxState]:
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
                             when: Optional[datetime.datetime] = None,
                             selected: Optional[MailboxState] = None) \
            -> Optional[MailboxState]:
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

    async def check_mailbox(self, selected: MailboxState,
                            housekeeping: bool = False) \
            -> Optional[MailboxState]:
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

    async def fetch_messages(self, selected: MailboxState,
                             sequences: SequenceSet,
                             attributes: AbstractSet[FetchAttribute]) \
            -> Tuple[ListT[Tuple[int, MessageStructure]],
                     Optional[MailboxState]]:
        """Get a list of :class:`MessageStructure` objects corresponding to
        given sequence set.

        :param selected: The name of the selected mailbox.
        :param sequences: Sequence set of message sequences or UIDs.
        :param attributes: Fetch attributes for the messages.

        """
        raise NotImplementedError

    async def search_mailbox(self, selected: MailboxState,
                             keys: ListT[SearchKey]) \
            -> Tuple[ListT[int], Optional[MailboxState]]:
        """Get the :class:`MessageInterface` objects in the current mailbox
        that meet the given search criteria.

        .. seealso:: `RFC 3501 7.2.5
        <https://tools.ietf.org/html/rfc3501#section-7.2.5>`_

        :param selected: The name of the selected mailbox.
        :param keys: Search keys specifying the message criteria.

        """
        raise NotImplementedError

    async def expunge_mailbox(self, selected: MailboxState) \
            -> Optional[MailboxState]:
        """All messages that are marked as deleted are immediately expunged
        from the mailbox.

        .. seealso:: `RFC 3501 6.4.3
        <https://tools.ietf.org/html/rfc3501#section-6.4.3>`_

        :param selected: The name of the selected mailbox.
        :raises pymap.exceptions.MailboxReadOnly:

        """
        raise NotImplementedError

    async def copy_messages(self, selected: MailboxState,
                            sequences: SequenceSet,
                            mailbox: str) \
            -> Optional[MailboxState]:
        """Copy a set of messages into the given mailbox.

        .. seealso:: `RFC 3501 6.4.7
        <https://tools.ietf.org/html/rfc3501#section-6.4.7>`_

        :param selected: The name of the selected mailbox.
        :param sequences: Sequence set of message sequences or UIDs.
        :param mailbox: Name of the mailbox to copy messages into.
        :raises pymap.exceptions.MailboxNotFound:

        """
        raise NotImplementedError

    async def update_flags(self, selected: MailboxState,
                           sequences: SequenceSet,
                           flag_set: AbstractSet[Flag],
                           mode: FlagOp = FlagOp.REPLACE,
                           silent: bool = False) \
            -> Optional[MailboxState]:
        """Update the flags for the given set of messages.

        .. seealso:: `RFC 3501 6.4.6
        <https://tools.ietf.org/html/rfc3501#section-6.4.6>`_

        :param selected: The name of the selected mailbox.
        :param sequences: Sequence set of message sequences or UIDs.
        :param flag_set: Set of flags to update.
        :param mode: Update mode for the flag set.
        :param silent: If True, flag changes should not be included in the
                       returned mailbox updates.

        """
        raise NotImplementedError
