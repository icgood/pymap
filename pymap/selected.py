
from collections import OrderedDict
from typing import Any, Type, Dict, Mapping, FrozenSet, NamedTuple, Optional, \
    Iterable, List, Tuple, SupportsBytes
from typing_extensions import Protocol

from .flags import SessionFlags
from .parsing.command import Command
from .parsing.primitives import ListP, Number
from .parsing.response import Response
from .parsing.response.specials import ExistsResponse, RecentResponse, \
    ExpungeResponse, FetchResponse
from .parsing.specials import FetchAttribute, Flag

__all__ = ['SelectedMailbox']

_Flags = FrozenSet[Flag]
_flags_attr = FetchAttribute(b'FLAGS')
_uid_attr = FetchAttribute(b'UID')


class _Message(NamedTuple):
    uid: int
    permanent_flags: _Flags


class _Previous(NamedTuple):
    recent: int
    messages: Dict[int, int]


class _OnForkProtocol(Protocol):

    def __call__(self, orig: 'SelectedMailbox',
                 forked: 'SelectedMailbox') -> None:
        ...


class SelectedMailbox:
    """Manages the updates to the current selected mailbox from other
    concurrent sessions.

    Args:
        name: The name of the selected mailbox.
        readonly: Indicates the mailbox is selected as read-only.
        session_flags: Session-only flags for the mailbox.
        on_fork: Callback passed in the before and after objects on a
            :meth:`.fork` call.

    """

    def __init__(self, name: str, readonly: bool,
                 session_flags: SessionFlags = None,
                 on_fork: _OnForkProtocol = None,
                 **kwargs: Any) -> None:
        super().__init__()
        self._name = name
        self._readonly = readonly
        self._session_flags = session_flags or SessionFlags()
        self._on_fork = on_fork
        self._kwargs = kwargs
        self._messages: Dict[int, _Flags] = OrderedDict()
        self._hashed: Optional[Mapping[int, int]] = None
        self._previous: Optional[_Previous] = None

    @property
    def name(self) -> str:
        """The name of the selected mailbox."""
        return self._name

    @property
    def readonly(self) -> bool:
        """Indicates the mailbox is selected as read-only."""
        return self._readonly

    @property
    def exists(self) -> int:
        """The total number of messages in the mailbox."""
        return len(self._messages)

    @property
    def recent(self) -> int:
        """The number of messages in the mailbox with ``\\Recent``."""
        return self.session_flags.count_recent()

    @property
    def session_flags(self) -> SessionFlags:
        """Session-only flags for the mailbox."""
        return self._session_flags

    @property
    def kwargs(self) -> Mapping[str, Any]:
        """Add keywords arguments to copy construction during :meth:`.fork`."""
        return {}

    def add_messages(self, *messages: _Message) -> None:
        """Add a message that exists in the mailbox. Shortcut for
        :meth:`.add_message`.

        Args:
            messages: The messages to add, each a tuple of UID and permanent
                flags.

        """
        for uid, permanent_flags in messages:
            all_flags = permanent_flags | self.session_flags.get(uid)
            self._messages[uid] = frozenset(all_flags)

    def remove_messages(self, *uids: int) -> None:
        """Remove messages that exist in the mailbox.

        Args:
            uids: The message UIDs.

        """
        for uid in uids:
            self._messages.pop(uid, None)

    def hide_fetch(self, *uids: int) -> None:
        """The flags currently associated with the given messages will not be
        shown as an untagged ``FETCH`` response.

        Args:
            uids: The message UIDs.

        """
        if self._previous:
            prev_messages = self._previous.messages
            for uid in uids:
                try:
                    flag_set = self._messages[uid]
                except KeyError:
                    pass
                else:
                    prev_messages[uid] = hash(flag_set)

    def fork(self) -> 'SelectedMailbox':
        """Return a copy of the current object. The forked copy retains info
        about the original, so that differences can be reported as untagged
        responses by :meth:`.add_untagged`.

        """
        cls: Type['SelectedMailbox'] = self.__class__
        copy = cls(self.name, self.readonly, self._session_flags,
                   self._on_fork, **self.kwargs)
        messages = [(uid, hash(flag_set))
                    for uid, flag_set in self._messages.items()]
        copy._previous = _Previous(self.recent, OrderedDict(messages))
        if self._on_fork:
            self._on_fork(self, copy)
        return copy

    def add_untagged(self, command: Command, response: Response) -> Response:
        """Updates since the last fork are added as untagged responses to the
        given tagged response.

        Args:
            command: The command being responded to.
            response: The tagged response to the command.

        """
        if self._previous and command.allow_updates:
            for untagged in self._compare(command, self._previous,
                                          self._messages):
                response.add_untagged(untagged)
        return response

    def _compare(self, command: Command, previous: _Previous,
                 current: Mapping[int, _Flags]) -> Iterable[Response]:
        is_uid: bool = getattr(command, 'uid', False)
        before_recent, before = previous
        before_uids = frozenset(before.keys())
        current_uids = frozenset(current.keys())
        sorted_uids = sorted(before_uids | current_uids)
        expunged_uids = before_uids - current_uids
        both_uids = before_uids & current_uids
        new_uids = current_uids - before_uids
        expunged: List[int] = []
        both: List[Tuple[int, int]] = []
        new: List[Tuple[int, int]] = []
        for seq, uid in enumerate(sorted_uids, 1):
            if uid in expunged_uids:
                self.session_flags.remove(uid)
                expunged.append(seq)
        for seq, uid in enumerate(sorted(current_uids), 1):
            if uid in both_uids:
                both.append((seq, uid))
            elif uid in new_uids:
                new.append((seq, uid))
        for seq in reversed(expunged):
            yield ExpungeResponse(seq)
        if new_uids:
            yield ExistsResponse(len(current))
        if before_recent != self.recent:
            yield RecentResponse(self.recent)
        for seq, uid in both:
            before_flags_hash = before[uid]
            current_flags = current[uid]
            if before_flags_hash != hash(current_flags):
                fetch_data: Dict[FetchAttribute, SupportsBytes] = {
                    _flags_attr: ListP(current_flags, sort=True)}
                if is_uid:
                    fetch_data[_uid_attr] = Number(uid)
                yield FetchResponse(seq, fetch_data)
        for seq, uid in new:
            current_flags = current[uid]
            fetch_data = {_flags_attr: ListP(current_flags, sort=True)}
            if is_uid:
                fetch_data[_uid_attr] = Number(uid)
            yield FetchResponse(seq, fetch_data)
