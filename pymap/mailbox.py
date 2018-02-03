# Copyright (c) 2018 Ian C. Good
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

"""Provides a basic implementation of the mailbox interface."""

from typing import Any, Optional, AbstractSet, FrozenSet, Dict, Tuple

from .flag import Recent, FlagOp
from .interfaces import MailboxInterface
from .parsing.specials import Flag
from .structure import MessageStructure, UpdateType

__all__ = ['BaseMailbox']

_Updates = Dict[int, Tuple[UpdateType, MessageStructure]]


class _Unique:
    pass


class BaseMailbox(MailboxInterface):
    """Implements some of the basic functionality of a mailbox, for backends
    that wish to save themselves some trouble.

    :param name: The name of the mailbox.
    :param permanent_flags: The permanent flags defined in the mailbox.
    :param session_flags: The session flags defined in the mailbox.
    :param readonly: If ``True``, the mailbox is read-only.
    :param uid_validity: The UID validity value for mailbox consistency.
    :param mailbox_session: Hashable value used to key the session flags in
                            the mailbox.
    :param mailbox_updates: Updates waiting to be reported to the client.

    """

    def __init__(self, name: str,
                 permanent_flags: Optional[AbstractSet[Flag]] = None,
                 session_flags: Optional[AbstractSet[Flag]] = None,
                 readonly: bool = False,
                 uid_validity: int = 0,
                 mailbox_session: Any = None,
                 mailbox_updates: _Updates = None):
        super().__init__()
        self._mailbox_session = mailbox_session or _Unique()
        self._updates = mailbox_updates or {}
        self._name = name
        self._readonly = readonly
        self._uid_validity = uid_validity
        self._permanent_flags = (
            frozenset(permanent_flags - {Recent})
            if permanent_flags else frozenset()
        )  # type: FrozenSet[Flag]
        self._session_flags = (
            frozenset((session_flags - self.permanent_flags) | {Recent})
            if session_flags else frozenset({Recent})
        )  # type: FrozenSet[Flag]

    @property
    def name(self) -> str:
        """The name of the mailbox."""
        return self._name

    @property
    def readonly(self) -> bool:
        """If ``True``, the mailbox is read-only."""
        return self._readonly

    @property
    def permanent_flags(self) -> FrozenSet[Flag]:
        """The permanent flags defined in the mailbox."""
        return self._permanent_flags

    @property
    def session_flags(self) -> FrozenSet[Flag]:
        """The session flags defined in the mailbox."""
        return self._session_flags

    @property
    def uid_validity(self) -> int:
        """The UID validity value for mailbox consistency."""
        return self._uid_validity

    @property
    def mailbox_session(self) -> Any:
        """Hashable value used to key the session flags in the mailbox."""
        return self._mailbox_session

    @property
    def flags(self) -> FrozenSet[Flag]:
        """All permanent and session flags defined in the mailbox."""
        return self.session_flags | self.permanent_flags

    @property
    def updates(self) -> _Updates:
        """Updates waiting to be reported to the client."""
        raise self._updates

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

    def get_flags(self, message: MessageStructure) -> FrozenSet[Flag]:
        """Get the full set of permanent and session flags.

        :param message: The message to get flags for.

        """
        session_flags = message.session_flags.get(self.mailbox_session)
        return frozenset(message.permanent_flags) | session_flags

    def update_flags(self, message: MessageStructure,
                     flag_set: AbstractSet[Flag],
                     flag_op: FlagOp = FlagOp.REPLACE) -> None:
        """Update the flags on a message in the mailbox. After this call,
        the ``message.permanent_flags`` set should be persisted by the
        backend.

        :param message: The message to set flags on.
        :param flag_set: The set of flags for the update operation.
        :param flag_op: Update mode for the flag set.

        """
        permanent_flags = frozenset(flag_set & self.permanent_flags)
        session_flags = frozenset(flag_set & self.session_flags)
        if flag_op == FlagOp.ADD:
            message.permanent_flags = message.permanent_flags | permanent_flags
        elif flag_op == FlagOp.DELETE:
            message.permanent_flags = message.permanent_flags - permanent_flags
        else:  # flag_op == FlagOp.REPLACE
            message.permanent_flags = permanent_flags
        message.session_flags.update(self.mailbox_session,
                                     session_flags, flag_op)

    def add_expunge(self, seq: int) -> None:
        """Add EXPUNGE update for the given sequence ID, indicating it has
        been permanently deleted.

        :param seq: The expunged message's sequence ID.

        """
        self.updates[seq] = (UpdateType.EXPUNGE, None)

    def add_fetch(self, seq: int, msg: MessageStructure) -> None:
        """Add FETCH update for the given message, indicating it has a
        different set of flags.

        :param seq: The updated message's sequence ID.
        :param msg: The message with the updated flags.

        """
        self.updates[seq] = (UpdateType.FETCH, msg)
