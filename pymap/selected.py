"""Utilities for managing the selected IMAP mailbox."""

from typing import Union, Dict, Optional, AbstractSet, Tuple, Any

from .flags import SessionFlags
from .parsing.primitives import ListP
from .parsing.response import Response
from .parsing.command import Command
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
        readonly: Indicates the mailbox is selected as read-only.
        session_flags: Session-only flags for the mailbox.
        updates: Update responses for the mailbox.

    """

    def __init__(self, name: str, readonly: bool,
                 session_flags: SessionFlags = None,
                 updates: Dict[int, '_Responses'] = None,
                 *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self._name = name
        self._readonly = readonly
        self._session_flags = session_flags or SessionFlags()
        self._updates: Dict[int, '_Responses'] = updates or {}
        self._previous: Optional[Tuple[int, int]] = None
        self._args = args
        self._kwargs = kwargs

    @property
    def name(self) -> str:
        """The name of the selected mailbox."""
        return self._name

    @property
    def exists(self) -> int:
        """The total number of messages in the mailbox."""
        raise NotImplementedError

    @property
    def recent(self) -> int:
        """The number of messages in the mailbox with ``\\Recent``."""
        return self.session_flags.count_recent()

    @property
    def readonly(self) -> bool:
        """Indicates the mailbox is selected as read-only."""
        return self._readonly

    @property
    def session_flags(self) -> SessionFlags:
        """Session-only flags for the mailbox."""
        return self._session_flags

    def fork(self) -> 'SelectedMailbox':
        """Return a copy of the current object. The new object will retain a
        snapshot of this object's :attr:`.exists` and :attr:`.recent` to be
        used by the :meth:`.drain_updates` method.

        """
        copy = self.__class__(self.name, self.readonly, self._session_flags,
                              self._updates, *self._args, **self._kwargs)
        copy._previous = (self.exists, self.recent)
        return copy

    def drain_updates(self, command: Command, response: Response) -> None:
        """Updates since the last command are added as untagged responses to
        the given tagged response.

        Args:
            command: The command being responded to.
            response: The tagged response to the command.

        """
        if self._previous and command.allow_updates:
            previous_exists, previous_recent = self._previous
            if previous_exists != self.exists:
                response.add_untagged(ExistsResponse(self.exists))
            if previous_recent != self.recent:
                response.add_untagged(RecentResponse(self.recent))
        for msg_seq in sorted(self._updates.keys()):
            response.add_untagged(self._updates[msg_seq])
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

    def remove_message(self, msg_seq: int, msg_uid: int) -> None:
        """Update the session to indicate an expunged message.

        Args:
            msg_seq: The sequence ID of the new message.
            msg_uid: The UID of the new message.

        """
        self._updates[msg_seq] = ExpungeResponse(msg_seq)
        self.session_flags.remove(msg_uid)
