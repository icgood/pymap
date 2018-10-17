"""Utilities for managing a IMAP mailboxes."""

from typing import TYPE_CHECKING, Union, Dict, Optional, Iterable, \
    AbstractSet, FrozenSet

from .flags import SessionFlags, FlagOp
from .interfaces.mailbox import MailboxInterface
from .interfaces.message import Message
from .parsing.primitives import ListP
from .parsing.response import Response
from .parsing.response.specials import ExistsResponse, RecentResponse, \
    FetchResponse, ExpungeResponse
from .parsing.specials import Flag, FetchAttribute
from .parsing.specials.flag import Recent

__all__ = ['MailboxSession', 'BaseMailbox']

if TYPE_CHECKING:
    _Responses = Union[ExistsResponse, RecentResponse,
                       FetchResponse, ExpungeResponse]


class MailboxSession:
    """Manages the updates to the current selected mailbox from other
    concurrent sessions.

    Args:
        name: The name of the selected mailbox.
        exists: The total number of messages in the mailbox.
        readonly: Indicates the mailbox is selected as read-only.
        session_flags: Session-only flags for the mailbox.
        updates: Update responses for the mailbox.

    """

    def __init__(self, name: str, exists: int, readonly: bool,
                 session_flags: SessionFlags = None,
                 updates: Dict[int, '_Responses'] = None) -> None:
        super().__init__()
        self._name = name
        self._exists = exists
        self._readonly = readonly
        self._session_flags = session_flags or SessionFlags()
        self._recent = self.session_flags.count_recent()
        self._updates: Dict[int, '_Responses'] = updates or {}
        self._previous: Optional['MailboxSession'] = None

    @property
    def name(self) -> str:
        """The name of the selected mailbox."""
        return self._name

    @property
    def exists(self) -> int:
        """The total number of messages in the mailbox."""
        return self._exists

    @property
    def recent(self) -> int:
        """The number of messages in the mailbox with ``\\Recent``."""
        return self._recent

    @property
    def readonly(self) -> bool:
        """Indicates the mailbox is selected as read-only."""
        return self._readonly

    @property
    def session_flags(self) -> SessionFlags:
        """Session-only flags for the mailbox."""
        return self._session_flags

    def __copy__(self) -> 'MailboxSession':
        ret = self.__class__(self.name, self.exists, self.readonly,
                             self.session_flags, self._updates)
        ret._previous = self._previous or self
        return ret

    def drain_updates(self) -> Iterable[Response]:
        """Return all the update responses since the last call to this method.

        """
        if self._previous:
            if self._previous.exists != self.exists:
                yield ExistsResponse(self.exists)
            if self._previous.recent != self.recent:
                yield RecentResponse(self.recent)
        for msg_seq in sorted(self._updates.keys()):
            yield self._updates[msg_seq]
        self._updates.clear()
        self._previous = None

    def add_fetch(self, msg_seq: int, flag_set: AbstractSet[Flag]) -> None:
        """Adds a ``FETCH`` response to the next :meth:`.get_updates` call.

        Args:
            msg_seq: The sequence ID of the updated message.
            flag_set: The flags associated with the message.

        """
        flags = sorted(flag_set)
        data = {FetchAttribute(b'FLAGS'): ListP(flags)}
        self._updates[msg_seq] = FetchResponse(msg_seq, data)

    def add_message(self, msg_seq: int, msg_uid: int,
                    flag_set: AbstractSet[Flag]) -> None:
        """Update the session to indicate a newly delivered message.

        Args:
            msg_seq: The sequence ID of the new message.
            msg_uid: The UID of the new message.
            flag_set: The flags associated with the message.

        """
        self.session_flags.add_recent(msg_uid)
        self.add_fetch(msg_seq, flag_set | {Recent})
        self._recent = self.session_flags.count_recent()
        self._exists += 1

    def remove_message(self, msg_seq: int, msg_uid: int) -> None:
        """Update the session to indicate an expunged message.

        Args:
            msg_seq: The sequence ID of the new message.
            msg_uid: The UID of the new message.

        """
        self._updates[msg_seq] = ExpungeResponse(msg_seq)
        self.session_flags.remove(msg_uid)
        self._recent = self.session_flags.count_recent()
        self._exists -= 1


class BaseMailbox(MailboxInterface):
    """Implements some of the basic functionality of a mailbox, for backends
    that wish to save themselves some trouble.

    Args:
        name: The name of the mailbox.
        permanent_flags: The permanent flags defined in the mailbox.
        session_flags: The session flags defined in the mailbox.
        readonly: If ``True``, the mailbox is read-only.
        uid_validity: The UID validity value for mailbox consistency.

    """

    def __init__(self, name: str,
                 permanent_flags: Optional[AbstractSet[Flag]] = None,
                 session_flags: Optional[AbstractSet[Flag]] = None,
                 readonly: bool = False,
                 uid_validity: int = 0) -> None:
        super().__init__()
        self._name = name
        self._readonly = readonly
        self._uid_validity = uid_validity
        self._permanent_flags: FrozenSet[Flag] = (
            frozenset(permanent_flags - {Recent})
            if permanent_flags else frozenset())
        self._session_flags: FrozenSet[Flag] = (
            frozenset((session_flags - self.permanent_flags) | {Recent})
            if session_flags else frozenset({Recent}))

    def update_flags(self, session: MailboxSession, message: Message,
                     flag_set: AbstractSet[Flag],
                     flag_op: FlagOp = FlagOp.REPLACE) \
            -> FrozenSet[Flag]:
        permanent_flags = frozenset(flag_set & self.permanent_flags)
        session_flags = frozenset(flag_set & self.session_flags)
        session.session_flags.update(message.uid, session_flags, flag_op)
        if flag_op == FlagOp.ADD:
            message.permanent_flags.update(permanent_flags)
        elif flag_op == FlagOp.DELETE:
            message.permanent_flags.difference_update(permanent_flags)
        else:  # flag_op == FlagOp.REPLACE
            message.permanent_flags.clear()
            message.permanent_flags.update(permanent_flags)
        return frozenset(message.permanent_flags)

    @property
    def name(self) -> str:
        return self._name

    @property
    def readonly(self) -> bool:
        return self._readonly

    @property
    def permanent_flags(self) -> FrozenSet[Flag]:
        return self._permanent_flags

    @property
    def session_flags(self) -> FrozenSet[Flag]:
        return self._session_flags

    @property
    def uid_validity(self) -> int:
        return self._uid_validity

    @property
    def flags(self) -> FrozenSet[Flag]:
        return self.session_flags | self.permanent_flags

    @property
    def exists(self) -> int:
        """Number of total messages in the mailbox.

        Raises:
            NotImplementedError: Must be implemented by sub-class.

        """
        raise NotImplementedError

    @property
    def recent(self) -> int:
        """Number of recent messages in the mailbox.

        Raises:
            NotImplementedError: Must be implemented by sub-class.

        """
        raise NotImplementedError

    @property
    def unseen(self) -> int:
        """Number of unseen messages in the mailbox.

        Raises:
            NotImplementedError: Must be implemented by sub-class.

        """
        raise NotImplementedError

    @property
    def first_unseen(self) -> Optional[int]:
        """The sequence number of the first unseen message.

        Raises:
            NotImplementedError: Must be implemented by sub-class.

        """
        raise NotImplementedError

    @property
    def next_uid(self) -> int:
        """The predicted next message UID.

        Raises:
            NotImplementedError: Must be implemented by sub-class.

        """
        raise NotImplementedError
