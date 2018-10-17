"""Utilities for managing the selected IMAP mailbox."""

from typing import Union, Dict, Optional, Iterable, AbstractSet

from .flags import SessionFlags
from .parsing.primitives import ListP
from .parsing.response import Response
from .parsing.response.specials import ExistsResponse, RecentResponse, \
    FetchResponse, ExpungeResponse
from .parsing.specials import Flag, FetchAttribute
from .parsing.specials.flag import Recent

__all__ = ['SelectedMailbox']

_Responses = Union[ExistsResponse, RecentResponse,
                   FetchResponse, ExpungeResponse]


class SelectedMailbox:
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
        self._previous: Optional['SelectedMailbox'] = None

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

    def __copy__(self) -> 'SelectedMailbox':
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
