
from typing import Any, TypeVar, Type, Dict, Mapping, MutableSet, FrozenSet, \
    NamedTuple, Optional, Iterable, List, Tuple, SupportsBytes
from weakref import WeakSet

from .concurrent import Event
from .flags import SessionFlags
from .parsing.command import Command
from .parsing.primitives import ListP, Number
from .parsing.response import Response, ResponseBye
from .parsing.response.code import UidValidity
from .parsing.response.specials import ExistsResponse, RecentResponse, \
    ExpungeResponse, FetchResponse
from .parsing.specials import FetchAttribute, Flag, SequenceSet

__all__ = ['SelectedSet', 'SelectedSnapshot', 'SelectedMailbox']

_SelectedT = TypeVar('_SelectedT', bound='SelectedMailbox')
_Flags = FrozenSet[Flag]
_Message = Tuple[int, _Flags]
_flags_attr = FetchAttribute(b'FLAGS')
_uid_attr = FetchAttribute(b'UID')


class SelectedSet:
    """Maintains a weak set of :class:`SelectedMailbox` objects that exist for
    a mailbox, across all sessions. This is useful for assigning the
    ``\\Recent`` flag, as well as notifying other sessions about updates.

    Args:
        updated: The event to notify when updates occur. Defaults to a new
            event using :mod:`asyncio` concurrency primitives.

    """

    def __init__(self, updated: Event = None) -> None:
        super().__init__()
        self._updated = updated or Event.for_asyncio()
        self._set: MutableSet['SelectedMailbox'] = WeakSet()

    @property
    def updated(self) -> Event:
        """The event to notify when updates occur."""
        return self._updated

    @property
    def any_selected(self) -> Optional['SelectedMailbox']:
        """A single, random instance in the set of selected mailbox objects."""
        for selected in self._set:
            return selected
        return None


class SelectedSnapshot(NamedTuple):
    """Holds a snapshot of the selected mailbox as of the last fork.

    Args:
        uid_validity: The UID validity of the selected mailbox.
        max_uid: The highest message UID in the mailbox.
        recent: The number of messages in the mailbox with ``\\Recent``.
        messages: The message UIDs mapped to flags.

    """

    uid_validity: Optional[int]
    max_uid: int
    recent: int
    messages: Dict[int, _Flags]

    @property
    def exists(self) -> int:
        """The total number of messages in the mailbox."""
        return len(self.messages)

    def iter_set(self, seq_set: SequenceSet) -> Iterable[Tuple[int, int]]:
        """Iterate through the given sequence set based on the message state at
        the last fork.

        Args:
            seq_set: Sequence set to convert to UID set.

        """
        if seq_set.uid:
            all_msgs = frozenset(seq_set.iter(self.max_uid))
        else:
            all_msgs = frozenset(seq_set.iter(self.exists))
        for seq, uid in enumerate(sorted(self.messages.keys()), 1):
            if seq_set.uid:
                if uid in all_msgs:
                    yield (seq, uid)
            elif seq in all_msgs:
                yield (seq, uid)


class SelectedMailbox:
    """Manages the updates to the current selected mailbox from other
    concurrent sessions.

    The current state of the selected mailbox will be written to this object by
    the backend implementation during each operation.  Then, when the operation
    completes, call :meth:`.fork` to make a fresh copy of the object and any
    untagged responses that should be added to the response.

    Args:
        name: The name of the selected mailbox.
        readonly: Indicates the mailbox is selected as read-only.
        session_flags: Session-only flags for the mailbox.
        selected_set: The ``self`` object and subsequent forked copies will be
            kept in in this set.

    """

    def __init__(self, name: str, readonly: bool,
                 session_flags: SessionFlags = None,
                 selected_set: SelectedSet = None,
                 **kwargs: Any) -> None:
        super().__init__()
        self._name = name
        self._readonly = readonly
        self._session_flags = session_flags or SessionFlags()
        self._selected_set = selected_set
        self._kwargs = kwargs
        self._uid_validity: Optional[int] = None
        self._max_uid = 0
        self._is_deleted = False
        self._messages: Dict[int, _Flags] = {}
        self._hashed: Optional[Mapping[int, int]] = None
        self._hide_expunged = False
        self._hidden: MutableSet[int] = set()
        self._snapshot: Optional[SelectedSnapshot] = None
        if selected_set:
            selected_set._set.add(self)

    @property
    def name(self) -> str:
        """The name of the selected mailbox."""
        return self._name

    @property
    def uid_validity(self) -> Optional[int]:
        """The UID validity of the selected mailbox."""
        return self._uid_validity

    @property
    def readonly(self) -> bool:
        """Indicates the mailbox is selected as read-only."""
        return self._readonly

    @property
    def max_uid(self) -> int:
        """The highest message UID in the mailbox."""
        return self._max_uid

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
    def snapshot(self) -> SelectedSnapshot:
        """A snapshot of the selected mailbox as of the last fork."""
        if not self._snapshot:
            raise RuntimeError()  # Must call fork() first.
        return self._snapshot

    @property
    def kwargs(self) -> Mapping[str, Any]:
        """Add keywords arguments to copy construction during :meth:`.fork`."""
        return {}

    def set_uid_validity(self, uid_validity: int) -> None:
        """Updates the UID validity of the selected mailbox.

        Args:
            uid_validity: The new UID validity value.

        """
        self._uid_validity = uid_validity

    def set_deleted(self) -> None:
        """Marks the selected mailbox as having been deleted."""
        self._is_deleted = True

    def add_messages(self, *messages: _Message) -> None:
        """Add a message that exists in the mailbox. Shortcut for
        :meth:`.add_message`.

        Args:
            messages: The messages to add, each a tuple of UID and permanent
                flags.

        """
        for uid, permanent_flags in messages:
            if uid > self._max_uid:
                self._max_uid = uid
            all_flags = permanent_flags | self.session_flags[uid]
            self._messages[uid] = frozenset(all_flags)

    def remove_messages(self, *uids: int) -> None:
        """Remove messages that exist in the mailbox.

        Args:
            uids: The message UIDs.

        """
        for uid in uids:
            self._messages.pop(uid, None)

    def hide_expunged(self) -> None:
        """No untagged ``EXPUNGE`` responses will be generated, and message
        sequence numbers will not be adjusted, until the next :meth:`.fork`.

        """
        self._hide_expunged = True

    def hide(self, *uids: int) -> None:
        """The messages with the given UIDs are marked as hidden, so that they
        will not produce untagged ``FETCH`` responses, until the next
        :meth:`.fork`.

        Args:
            uids: The message UIDs.

        """
        self._hidden |= frozenset(uids)

    def fork(self: _SelectedT, command: Command) \
            -> Tuple[_SelectedT, Iterable[Response]]:
        """Compares the state of the current object to that of the last fork,
        returning the untagged responses that reflect any changes. A new copy
        of the object is also returned, ready for the next command.

        Args:
            command: The command that was finished.

        """
        cls: Type[_SelectedT] = type(self)
        copy = cls(self.name, self.readonly, self._session_flags,
                   self._selected_set, **self.kwargs)
        copy._uid_validity = self._uid_validity
        copy._max_uid = self._max_uid
        copy._snapshot = SelectedSnapshot(self.uid_validity, self.max_uid,
                                          self.recent, self._messages)
        if self._selected_set:
            self._selected_set._set.discard(self)
            self._selected_set._set.add(copy)
        if self._snapshot:
            return copy, self._compare(command)
        else:
            return copy, []

    def _compare(self, command: Command) -> Iterable[Response]:
        is_uid: bool = getattr(command, 'uid', False)
        before_uidval, _, before_recent, before = self.snapshot
        current = self._messages
        uidval = self.uid_validity
        if self._is_deleted:
            yield ResponseBye(b'Selected mailbox deleted.')
            return
        elif uidval is not None and before_uidval != uidval:
            yield ResponseBye(b'UID validity changed.', UidValidity(uidval))
            return
        before_uids = frozenset(before.keys())
        current_uids = frozenset(current.keys())
        expunged_uids = before_uids - current_uids
        both_uids = before_uids & current_uids
        new_uids = current_uids - before_uids
        both: List[Tuple[int, int]] = []
        new: List[Tuple[int, int]] = []
        if self._hide_expunged:
            for uid in expunged_uids:
                current[uid] = before[uid]
            current_uids = frozenset(current.keys())
        else:
            expunged: List[int] = []
            sorted_before_uids = sorted(before_uids)
            for seq, uid in enumerate(sorted_before_uids, 1):
                if uid in expunged_uids:
                    del self.session_flags[uid]
                    expunged.append(seq)
            for seq in reversed(expunged):
                yield ExpungeResponse(seq)
        for seq, uid in enumerate(sorted(current_uids), 1):
            if uid in both_uids:
                both.append((seq, uid))
            elif uid in new_uids:
                new.append((seq, uid))
        if new_uids:
            yield ExistsResponse(len(current_uids))
        if before_recent != self.recent:
            yield RecentResponse(self.recent)
        for seq, uid in both:
            if uid in self._hidden:
                continue
            before_flags = before[uid]
            current_flags = current[uid]
            if hash(before_flags) != hash(current_flags):
                fetch_data: Dict[FetchAttribute, SupportsBytes] = {
                    _flags_attr: ListP(current_flags, sort=True)}
                if is_uid:
                    fetch_data[_uid_attr] = Number(uid)
                yield FetchResponse(seq, fetch_data)
        for seq, uid in new:
            if uid not in self._hidden:
                current_flags = current[uid]
                fetch_data = {_flags_attr: ListP(current_flags, sort=True)}
                if is_uid:
                    fetch_data[_uid_attr] = Number(uid)
                yield FetchResponse(seq, fetch_data)
