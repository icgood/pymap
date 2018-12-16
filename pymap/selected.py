
from itertools import chain
from typing import Any, TypeVar, Type, Optional, Tuple, Dict, Mapping, \
    Set, MutableSet, AbstractSet, FrozenSet, NamedTuple, Iterable, List, \
    SupportsBytes
from weakref import WeakSet

from .concurrent import Event
from .context import subsystem
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

    __slots__ = ['_set', '_updated']

    def __init__(self) -> None:
        super().__init__()
        self._set: MutableSet['SelectedMailbox'] = WeakSet()
        self._updated = subsystem.get().new_event()

    def add(self, selected: 'SelectedMailbox', *,
            replace: 'SelectedMailbox' = None) -> None:
        if replace is not None:
            self._set.discard(replace)
        self._set.add(selected)

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
        for selected in self._set:
            if not selected.readonly:
                return selected
        return None


class SelectedSnapshot(NamedTuple):
    """Keeps a snapshot of the state of the selected mailbox at the time of
    the last :meth:`.fork`.

    """
    uid_validity: Optional[int]
    next_uid: int
    recent_uids: FrozenSet[int]
    uids: FrozenSet[int]
    msg_flags: FrozenSet[Tuple[int, FrozenSet[Flag]]]
    session_flags: FrozenSet[Tuple[int, FrozenSet[Flag]]]

    @property
    def max_seq(self) -> int:
        """The highest message sequence in the mailbox."""
        return len(self.uids)

    @property
    def max_uid(self) -> int:
        """The highest message UID in the mailbox."""
        return self.next_uid - 1


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
        self._uids: Set[int] = set()
        self._msg_flags: Set[Tuple[int, FrozenSet[Flag]]] = set()
        self._cache: Dict[int, CachedMessage] = {}
        self._hide_expunged = False
        self._silenced_flags: Set[Tuple[int, FrozenSet[Flag]]] = set()
        self._silenced_sflags: Set[Tuple[int, FrozenSet[Flag]]] = set()
        self._snapshot: Optional[SelectedSnapshot] = None
        if selected_set:
            selected_set.add(self)

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
        return len(self._uids)

    @property
    def recent(self) -> int:
        """The number of messages in the mailbox with ``\\Recent``."""
        recent_uids = self.session_flags.recent_uids
        if self._hide_expunged:
            return len(recent_uids)
        else:
            return len(recent_uids & self._uids)

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

    def set_messages(self, messages: Iterable[CachedMessage]) -> None:
        """Add a message that exists in the mailbox.

        Args:
            messages: The cached message objects to add.

        """
        self._cache.update({msg.uid: msg for msg in messages})
        self._uids = {msg.uid for msg in messages}
        self._msg_flags = {msg.flags_key for msg in messages}

    def get_message(self, uid: int) -> Optional[CachedMessage]:
        """Return the cached message for the given message UID.

        Args:
            uid: The message UID.

        """
        return self._cache.get(uid)

    def silence(self, seq_set: SequenceSet, flag_set: Iterable[Flag],
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
        cache = self._cache
        cached_uids = frozenset(cache.keys())
        for _, uid in self.iter_set(seq_set, cached_uids):
            cached_msg = cache.get(uid)
            if cached_msg is not None:
                msg_flags = cached_msg.get_flags()
                msg_sflags = session_flags.get(uid)
                updated_flags = flag_op.apply(msg_flags, permanent_flag_set)
                updated_sflags = flag_op.apply(msg_sflags, session_flag_set)
                if msg_flags != updated_flags:
                    self._silenced_flags.add((uid, updated_flags))
                if msg_sflags != updated_sflags:
                    self._silenced_sflags.add((uid, updated_sflags))

    def hide_expunged(self) -> None:
        """No untagged ``EXPUNGE`` responses will be generated, and message
        sequence numbers will not be adjusted, until the next :meth:`.fork`.

        """
        self._hide_expunged = True

    def iter_set(self, seq_set: SequenceSet, uids: AbstractSet[int]) \
            -> Iterable[Tuple[int, int]]:
        """Iterate through the given sequence set based on the message state at
        the last fork.

        Args:
            seq_set: Sequence set to convert to UID set.
            uids: The current set of UIDs in the mailbox.

        """
        if self._hide_expunged:
            all_uids = uids | self.snapshot.uids
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
            uids = frozenset(self.snapshot.uids | self._uids)
            msg_flags = frozenset(self.snapshot.msg_flags | self._msg_flags)
        else:
            uids = frozenset(self._uids)
            msg_flags = frozenset(self._msg_flags)
        recent = frozenset(self.session_flags.recent_uids)
        session_flags = frozenset(self.session_flags.flags.items())
        copy._cache = self._cache
        copy._snapshot = SelectedSnapshot(self.uid_validity, self.next_uid,
                                          recent, uids, msg_flags,
                                          session_flags)
        if self._selected_set:
            self._selected_set.add(copy, replace=self)
        if self._snapshot:
            return copy, self._compare(command)
        else:
            return copy, []

    @property
    def snapshot(self) -> SelectedSnapshot:
        """A snapshot of the selected mailbox at the time of the last
        :meth:`.fork`.

        """
        if not self._snapshot:
            raise RuntimeError()  # Must call fork() first.
        return self._snapshot

    def _compare(self, command: Command) -> Iterable[Response]:
        is_uid: bool = getattr(command, 'uid', False)
        session_flags = self.session_flags
        uidval = self.uid_validity
        snapshot = self.snapshot
        if self._is_deleted:
            yield ResponseBye(b'Selected mailbox deleted.')
            return
        elif uidval is not None and snapshot.uid_validity != uidval:
            yield ResponseBye(b'UID validity changed.', UidValidity(uidval))
            return
        before_flags = snapshot.msg_flags
        current_flags = self._msg_flags
        current_sflags = frozenset(self.session_flags.flags.items())
        before_uids = snapshot.uids
        current_uids = self._uids
        expunged_uids = before_uids - current_uids
        new_uids = current_uids - before_uids
        if self._hide_expunged:
            current_uids.update(expunged_uids)
        else:
            expunged: List[int] = []
            sorted_before_uids = sorted(before_uids)
            for seq, uid in enumerate(sorted_before_uids, 1):
                if uid in expunged_uids:
                    expunged.append(seq)
            for seq in reversed(expunged):
                yield ExpungeResponse(seq)
        if new_uids:
            yield ExistsResponse(len(current_uids))
        if len(snapshot.recent_uids) != self.recent:
            yield RecentResponse(self.recent)
        current_seqs = {uid: seq for seq, uid in
                        enumerate(sorted(current_uids), 1)}
        new_flags = (current_flags - before_flags - self._silenced_flags)
        new_recent = (session_flags.recent_uids - snapshot.recent_uids)
        new_sflags = (current_sflags - snapshot.session_flags -
                      self._silenced_sflags)
        fetch_uids = frozenset(chain((uid for uid, _ in new_flags),
                                     (uid for uid, _ in new_sflags),
                                     new_recent))
        for uid in sorted(fetch_uids):
            seq = current_seqs[uid]
            msg_flags = self._cache[uid].get_flags(session_flags)
            fetch_data: Dict[FetchAttribute, SupportsBytes] = {
                _flags_attr: ListP(msg_flags, sort=True)}
            if is_uid:
                fetch_data[_uid_attr] = Number(uid)
            yield FetchResponse(seq, fetch_data)
