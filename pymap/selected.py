
from typing import Any, TypeVar, Type, Dict, Mapping, MutableSet, FrozenSet, \
    NamedTuple, Optional, Iterable, List, Tuple, SupportsBytes
from weakref import WeakSet

from .concurrent import Event
from .flags import FlagOp, PermanentFlags, SessionFlags
from .interfaces.message import CachedMessage
from .parsing.command import Command
from .parsing.primitives import ListP, Number
from .parsing.response import Response, ResponseBye
from .parsing.response.code import UidValidity
from .parsing.response.specials import ExistsResponse, RecentResponse, \
    ExpungeResponse, FetchResponse
from .parsing.specials import FetchAttribute, Flag, SequenceSet

__all__ = ['SelectedSet', 'SelectedMailbox', 'SelectedT']

#: Type variable with an upper bound of :class:`SelectedMailbox`.
SelectedT = TypeVar('SelectedT', bound='SelectedMailbox')

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

    __slots__ = ['set', '_updated']

    def __init__(self, updated: Event = None) -> None:
        super().__init__()
        self.set: MutableSet['SelectedMailbox'] = WeakSet()
        self._updated = updated or Event.for_asyncio()

    @property
    def updated(self) -> Event:
        """The event to notify when updates occur."""
        return self._updated

    @property
    def any_selected(self) -> Optional['SelectedMailbox']:
        """A single, random object in the set of selected mailbox objects.
        Selected mailbox object's marked :attr:`~SelectedMailbox.readonly`
        will not be chosen.

        """
        for selected in self.set:
            if not selected.readonly:
                return selected
        return None


class _SelectedSnapshot(NamedTuple):
    uid_validity: Optional[int]
    next_uid: int
    recent: int
    messages: Dict[int, int]


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
        permanent_flags: The defined permanent flags for the mailbox.
        session_flags: Session-only flags for the mailbox.
        selected_set: The ``self`` object and subsequent forked copies will be
            kept in in this set.

    """

    def __init__(self, name: str, readonly: bool,
                 permanent_flags: PermanentFlags,
                 session_flags: SessionFlags,
                 selected_set: SelectedSet = None,
                 **kwargs: Any) -> None:
        super().__init__()
        self._name = name
        self._readonly = readonly
        self._permanent_flags = permanent_flags
        self._session_flags = session_flags
        self._selected_set = selected_set
        self._kwargs = kwargs
        self._uid_validity: Optional[int] = None
        self._next_uid = 1
        self._is_deleted = False
        self._messages: Dict[int, int] = {}
        self._cache: Dict[int, CachedMessage] = {}
        self._hide_expunged = False
        self._snapshot: Optional[_SelectedSnapshot] = None
        if selected_set:
            selected_set.set.add(self)

    @property
    def name(self) -> str:
        """The name of the selected mailbox."""
        return self._name

    @property
    def uid_validity(self) -> Optional[int]:
        """The UID validity of the selected mailbox."""
        return self._uid_validity

    @uid_validity.setter
    def uid_validity(self, uid_validity: int) -> None:
        self._uid_validity = uid_validity

    @property
    def next_uid(self) -> int:
        """The predicted next message UID value of the mailbox."""
        return self._next_uid

    @next_uid.setter
    def next_uid(self, next_uid: int) -> None:
        self._next_uid = next_uid

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
        recent_uids = self.session_flags.recent_uids
        if self._hide_expunged:
            return len(recent_uids)
        else:
            current_uids = frozenset(self._messages.keys())
            return len(recent_uids & current_uids)

    @property
    def permanent_flags(self) -> PermanentFlags:
        """The defined permanent flags for the mailbox."""
        return self._permanent_flags

    @property
    def session_flags(self) -> SessionFlags:
        """Session-only flags for the mailbox."""
        return self._session_flags

    @property
    def kwargs(self) -> Mapping[str, Any]:
        """Add keywords arguments to copy construction during :meth:`.fork`."""
        return {}

    def set_deleted(self) -> None:
        """Marks the selected mailbox as having been deleted."""
        self._is_deleted = True

    def add_messages(self, messages: Iterable[CachedMessage]) -> None:
        """Add a message that exists in the mailbox.

        Args:
            messages: The cached message objects to add.

        """
        _cache = self._cache
        _messages = self._messages
        session_flags = self.session_flags
        for msg in messages:
            uid = msg.uid
            _cache[uid] = msg
            _messages[uid] = hash(msg.get_flags(session_flags))

    def get_message(self, uid: int) -> Optional[CachedMessage]:
        """Return the cached message for the given message UID.

        Args:
            uid: The message UID.

        """
        return self._cache.get(uid)

    def silence(self, seq_set: SequenceSet, flag_set: FrozenSet[Flag],
                flag_op: FlagOp) -> None:
        """Runs the flags update against the cached flags, to prevent untagged
        FETCH responses unless other updates have occurred.

        For example, if a session adds ``\\Deleted`` and calls this method,
        the FETCH response will be silenced. But if another added ``\\Seen``
        at the same time, the FETCH response will be sent.

        Args:
            seq_set: Sequence set to be updated.
            flag_set: The set of flags for the update operation.
            flag_op: The mode to change the flags.

        """
        session_flags = self.session_flags
        permanent_flag_set = self.permanent_flags & flag_set
        session_flag_set = session_flags & flag_set
        defined_flag_set = permanent_flag_set | session_flag_set
        messages = self.snapshot.messages
        cache = self._cache
        cached_uids = frozenset(cache.keys())
        for _, uid in self.iter_set(seq_set, cached_uids):
            cached_msg = cache.get(uid)
            if cached_msg is not None:
                cached_flags = cached_msg.get_flags(session_flags)
                updated_flags = flag_op.apply(cached_flags, defined_flag_set)
                messages[uid] = hash(updated_flags)

    def hide_expunged(self) -> None:
        """No untagged ``EXPUNGE`` responses will be generated, and message
        sequence numbers will not be adjusted, until the next :meth:`.fork`.

        """
        self._hide_expunged = True

    def iter_set(self, seq_set: SequenceSet, uids: FrozenSet[int]) \
            -> Iterable[Tuple[int, int]]:
        """Iterate through the given sequence set based on the message state at
        the last fork.

        Args:
            seq_set: Sequence set to convert to UID set.
            uids: The current set of UIDs in the mailbox.

        """
        if self._hide_expunged:
            snapshot_uids = frozenset(self.snapshot.messages.keys())
            all_uids = uids | snapshot_uids
        else:
            all_uids = uids
        sorted_uids = sorted(all_uids)
        if seq_set.uid:
            try:
                max_uid = sorted_uids[-1]
            except IndexError:
                max_uid = 0
            all_idx = frozenset(seq_set.iter(max_uid))
        else:
            all_idx = frozenset(seq_set.iter(len(all_uids)))
        for seq, uid in enumerate(sorted_uids, 1):
            idx = uid if seq_set.uid else seq
            if idx in all_idx:
                yield (seq, uid)

    def fork(self: SelectedT, command: Command) \
            -> Tuple[SelectedT, Iterable[Response]]:
        """Compares the state of the current object to that of the last fork,
        returning the untagged responses that reflect any changes. A new copy
        of the object is also returned, ready for the next command.

        Args:
            command: The command that was finished.

        """
        cls: Type[SelectedT] = type(self)
        copy = cls(self.name, self.readonly, self._permanent_flags,
                   self._session_flags, self._selected_set, **self.kwargs)
        if self._hide_expunged and self._snapshot:
            messages = self.snapshot.messages.copy()
            messages.update(self._messages)
        else:
            messages = self._messages
        copy._cache = self._cache
        copy._snapshot = _SelectedSnapshot(self.uid_validity, self.next_uid,
                                           self.recent, messages)
        if self._selected_set:
            self._selected_set.set.discard(self)
            self._selected_set.set.add(copy)
        if self._snapshot:
            return copy, self._compare(command)
        else:
            return copy, []

    @property
    def snapshot(self) -> _SelectedSnapshot:
        if not self._snapshot:
            raise RuntimeError()  # Must call fork() first.
        return self._snapshot

    def _compare(self, command: Command) -> Iterable[Response]:
        is_uid: bool = getattr(command, 'uid', False)
        before_uidval, _, before_recent, before = self.snapshot
        session_flags = self.session_flags
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
                    session_flags.remove(uid)
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
            before_hash = before[uid]
            current_hash = current[uid]
            if before_hash != current_hash:
                current_flags = self._cache[uid].get_flags(session_flags)
                fetch_data: Dict[FetchAttribute, SupportsBytes] = {
                    _flags_attr: ListP(current_flags, sort=True)}
                if is_uid:
                    fetch_data[_uid_attr] = Number(uid)
                yield FetchResponse(seq, fetch_data)
        for seq, uid in new:
            current_flags = self._cache[uid].get_flags(session_flags)
            fetch_data = {_flags_attr: ListP(current_flags, sort=True)}
            if is_uid:
                fetch_data[_uid_attr] = Number(uid)
            yield FetchResponse(seq, fetch_data)
