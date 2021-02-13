
from __future__ import annotations

from bisect import bisect_right
from collections.abc import Iterable, MutableSet, Sequence, Set
from itertools import chain, groupby, islice
from typing import Any, Optional
from weakref import WeakSet

from .flags import FlagOp, PermanentFlags, SessionFlags
from .interfaces.message import CachedMessage, FlagsKey
from .parsing.command import Command
from .parsing.primitives import List, Number
from .parsing.response import UntaggedResponse, ResponseBye
from .parsing.response.specials import ExistsResponse, RecentResponse, \
    ExpungeResponse, FetchResponse
from .parsing.specials import ObjectId, FetchAttribute, FetchValue, \
    Flag, SequenceSet

__all__ = ['SelectedSet', 'SynchronizedMessages', 'SelectedMailbox']

_flags_attr = FetchAttribute(b'FLAGS')
_uid_attr = FetchAttribute(b'UID')


class SelectedSet:
    """Maintains a weak set of :class:`SelectedMailbox` objects that exist for
    a mailbox, across all sessions. This is useful for assigning the
    ``\\Recent`` flag, as well as notifying other sessions about updates.

    """

    __slots__ = ['_set']

    def __init__(self) -> None:
        super().__init__()
        self._set: MutableSet[SelectedMailbox] = WeakSet()

    def add(self, selected: SelectedMailbox, *,
            replace: SelectedMailbox = None) -> None:
        """Add a new selected mailbox object to the set, which may then be
        returned by :meth:`.any_selected`.

        Args:
            selected: The new selected mailbox object.
            replace: An existing selected mailbox object that should be removed
                from the weak set.

        """
        if replace is not None:
            self._set.discard(replace)
        self._set.add(selected)

    @property
    def any_selected(self) -> Optional[SelectedMailbox]:
        """A single, random object in the set of selected mailbox objects.
        Selected mailbox object's marked :attr:`~SelectedMailbox.readonly`
        will not be chosen.

        """
        for selected in self._set:
            if not selected.readonly:
                return selected
        return None


class _Frozen:

    def __init__(self, selected: SelectedMailbox) -> None:
        super().__init__()
        messages = selected.messages
        session_flags = selected.session_flags
        self.is_deleted = selected._is_deleted
        self.uids = messages._uids.copy()
        self.seqs_cache = messages._seqs_cache.copy()
        self.flags = messages._flags_key_set.copy()
        self.recent = session_flags.recent_uids & self.uids
        self.sflags = frozenset(session_flags.flags.items())


class SynchronizedMessages:
    """Manages the message data that has been synchronized with the client."""

    def __init__(self) -> None:
        super().__init__()
        self._uids: set[int] = set()
        self._sorted: list[int] = []
        self._seqs_cache: dict[int, int] = {}
        self._cache: dict[int, CachedMessage] = {}
        self._flags_key_map: dict[int, FlagsKey] = {}
        self._flags_key_set: set[FlagsKey] = set()
        self._pending_remove: set[int] = set()

    @property
    def exists(self) -> int:
        """The total number of messages in the mailbox."""
        return len(self._uids)

    @property
    def max_uid(self) -> int:
        """The highest message UID value of the mailbox."""
        try:
            return self._sorted[-1]
        except IndexError:
            return 0

    def _update(self, messages: Iterable[CachedMessage]) -> None:
        lowest_idx: Optional[int] = None
        for msg in messages:
            msg_uid = msg.uid
            if msg_uid not in self._uids:
                self._uids.add(msg_uid)
                idx = bisect_right(self._sorted, msg_uid)
                if lowest_idx is None or lowest_idx > idx:
                    lowest_idx = idx
                self._sorted.insert(idx, msg_uid)
            self._cache[msg_uid] = msg
            new_flags_key = msg.flags_key
            old_flags_key = self._flags_key_map.get(msg_uid)
            if old_flags_key is not None:
                self._flags_key_set.discard(old_flags_key)
            self._flags_key_map[msg_uid] = new_flags_key
            self._flags_key_set.add(new_flags_key)
        if lowest_idx is not None:
            needs_reset = islice(self._sorted, lowest_idx, len(self._sorted))
            for seq, uid in enumerate(needs_reset, lowest_idx + 1):
                self._seqs_cache[uid] = seq

    def _remove(self, uids: Iterable[int], pending: bool) -> None:
        if pending:
            self._pending_remove.update(uids)
        else:
            any_removed = False
            for msg_uid in chain(uids, self._pending_remove):
                try:
                    self._uids.remove(msg_uid)
                except KeyError:
                    pass
                else:
                    flags_key = self._flags_key_map[msg_uid]
                    self._flags_key_set.remove(flags_key)
                    del self._flags_key_map[msg_uid]
                    del self._cache[msg_uid]
                    any_removed = True
            self._pending_remove.clear()
            if any_removed:
                self._sorted = sorted_uids = sorted(self._uids)
                self._seqs_cache = {uid: seq for seq, uid in
                                    enumerate(sorted_uids, 1)}

    def get(self, uid: int) -> Optional[CachedMessage]:
        """Return the given cached message.

        Args:
            uid: The message UID.

        """
        return self._cache.get(uid)

    def get_uids(self, seq_set: SequenceSet) -> Sequence[tuple[int, int]]:
        """Return the message sequence numbers and their UIDs for the given
        sequence set.

        Args:
            seq_set: The message sequence set.

        """
        if seq_set.uid:
            all_uids = seq_set.flatten(self.max_uid) & self._uids
            return [(seq, uid) for seq, uid in enumerate(self._sorted, 1)
                    if uid in all_uids]
        else:
            all_seqs = seq_set.flatten(self.exists)
            return [(seq, uid) for seq, uid in enumerate(self._sorted, 1)
                    if seq in all_seqs]

    def get_all(self, seq_set: SequenceSet) \
            -> Sequence[tuple[int, CachedMessage]]:
        """Return the cached messages, and their sequence numbers, for the
        given sequence set.

        Args:
            seq_set: The message sequence set.

        """
        if seq_set.uid:
            all_uids = seq_set.flatten(self.max_uid) & self._uids
            return [(seq, self._cache[uid])
                    for seq, uid in enumerate(self._sorted, 1)
                    if uid in all_uids]
        else:
            all_seqs = seq_set.flatten(self.exists)
            return [(seq, self._cache[uid])
                    for seq, uid in enumerate(self._sorted, 1)
                    if seq in all_seqs]


class SelectedMailbox:
    """Manages the updates to the current selected mailbox from other
    concurrent sessions.

    The current state of the selected mailbox will be written to this object by
    the backend implementation during each operation.  Then, when the operation
    completes, call :meth:`.fork` to make a fresh copy of the object and any
    untagged responses that should be added to the response.

    Args:
        mailbox_id: The globally unique identifier of the selected mailbox.
        readonly: Indicates the mailbox is selected as read-only.
        permanent_flags: The defined permanent flags for the mailbox.
        session_flags: Session-only flags for the mailbox.
        selected_set: The ``self`` object and subsequent forked copies will be
            kept in in this set.

    """

    __slots__ = ['_mailbox_id', '_readonly', '_permanent_flags',
                 '_session_flags', '_selected_set', '_kwargs', '_lookup',
                 '_mod_sequence', '_is_deleted', '_hide_expunged',
                 '_silenced_flags', '_silenced_sflags', '_prev', '_messages',
                 '__weakref__']

    def __init__(self, mailbox_id: ObjectId, readonly: bool,
                 permanent_flags: PermanentFlags,
                 session_flags: SessionFlags,
                 selected_set: SelectedSet = None,
                 lookup: Any = None, **kwargs: Any) -> None:
        super().__init__()
        self._mailbox_id = mailbox_id
        self._readonly = readonly
        self._permanent_flags = permanent_flags
        self._session_flags = session_flags
        self._selected_set = selected_set
        self._kwargs = kwargs
        self._lookup: Any = lookup
        self._mod_sequence = kwargs.get('_mod_sequence')
        self._is_deleted = False
        self._hide_expunged = False
        self._silenced_flags: set[tuple[int, frozenset[Flag]]] = set()
        self._silenced_sflags: set[tuple[int, frozenset[Flag]]] = set()
        self._prev: Optional[_Frozen] = kwargs.get('_prev')
        try:
            self._messages: SynchronizedMessages = kwargs['_messages']
        except KeyError:
            self._messages = SynchronizedMessages()
        if selected_set is not None:
            selected_set.add(self)

    @property
    def mailbox_id(self) -> ObjectId:
        """The selected mailbox object ID.

        See Also:
            :attr:`~pymap.interfaces.mailbox.MailboxInterface.mailbox_id`

        """
        return self._mailbox_id

    @property
    def lookup(self) -> Any:
        """The lookup value, if any, needed by backends that cannot lookup
        mailboxes by :attr:`.mailbox_id`. A typical lookup value might be the
        name of the mailbox.

        """
        return self._lookup

    @lookup.setter
    def lookup(self, lookup: Any) -> None:
        self._lookup = lookup

    @property
    def mod_sequence(self) -> Any:
        """The highest modification sequence of the mailbox."""
        return self._mod_sequence

    @mod_sequence.setter
    def mod_sequence(self, mod_sequence: Any) -> None:
        self._mod_sequence = mod_sequence

    @property
    def hide_expunged(self) -> bool:
        """If True, no untagged ``EXPUNGE`` responses will be generated, and
        message sequence numbers will not be adjusted, until the next
        :meth:`.fork`.

        """
        return self._hide_expunged

    @hide_expunged.setter
    def hide_expunged(self, hide_expunged: bool) -> None:
        self._hide_expunged = hide_expunged

    def add_updates(self, messages: Iterable[CachedMessage],
                    expunged: Iterable[int]) -> None:
        """Update the messages in the selected mailboxes. The ``messages``
        should include non-expunged messages in the mailbox that should be
        checked for updates. The ``expunged`` argument is the set of UIDs that
        have been expunged from the mailbox.

        In an optimized implementation, ``messages`` only includes new messages
        or messages with metadata updates.  This minimizes the comparison
        needed to determine what untagged responses are necessary. The
        :attr:`.mod_sequence` attribute may be used to support this
        optimization.

        If a backend implementation lacks the ability to determine the subset
        of messages that have been updated, it should instead use
        :meth:`.set_messages`.

        Args:
            messages: The cached message objects to add.
            expunged: The set of message UIDs that have been expunged.

        """
        self._messages._update(messages)
        self._messages._remove(expunged, self._hide_expunged)
        if not self._hide_expunged:
            self._session_flags.remove(expunged)

    def set_messages(self, messages: Sequence[CachedMessage]) -> None:
        """This is the non-optimized alternative to :meth:`.add_updates` for
        backend implementations that cannot detect their own updates and must
        instead compare the entire state of the mailbox.

        The ``messages`` list should contain the entire set of messages in the
        mailbox, ordered by UID. Any UID that previously existed and is not
        included in ``messages`` will be expunged.

        Args:
            messages: The entire set of cached message objects.

        """
        uids = {msg.uid for msg in messages}
        expunged = self._messages._uids - uids
        return self.add_updates(messages, expunged)

    @property
    def readonly(self) -> bool:
        """Indicates the mailbox is selected as read-only."""
        return self._readonly

    @property
    def messages(self) -> SynchronizedMessages:
        """The messages in the mailbox, as synchronized with the client."""
        return self._messages

    @property
    def permanent_flags(self) -> PermanentFlags:
        """The defined permanent flags for the mailbox."""
        return self._permanent_flags

    @property
    def session_flags(self) -> SessionFlags:
        """Session-only flags for the mailbox."""
        return self._session_flags

    def set_deleted(self) -> None:
        """Marks the selected mailbox as having been deleted."""
        self._is_deleted = True

    def silence(self, seq_set: SequenceSet, flag_set: Set[Flag],
                flag_op: FlagOp) -> None:
        """Runs the flags update against the cached flags, to prevent untagged
        FETCH responses unless other updates have occurred.

        For example, if a session adds ``\\Deleted`` and calls this method,
        the FETCH response will be silenced. But if another added ``\\Seen``
        at the same time, the FETCH response will be sent.

        Args:
            seq_set: The sequence set of messages.
            flag_set: The set of flags for the update operation.
            flag_op: The mode to change the flags.

        """
        session_flags = self.session_flags
        permanent_flag_set = self.permanent_flags & flag_set
        session_flag_set = session_flags & flag_set
        for seq, msg in self._messages.get_all(seq_set):
            msg_flags = msg.permanent_flags
            msg_sflags = session_flags.get(msg.uid)
            updated_flags = flag_op.apply(msg_flags, permanent_flag_set)
            updated_sflags = flag_op.apply(msg_sflags, session_flag_set)
            if msg_flags != updated_flags:
                self._silenced_flags.add((msg.uid, updated_flags))
            if msg_sflags != updated_sflags:
                self._silenced_sflags.add((msg.uid, updated_sflags))

    def fork(self, command: Command) \
            -> tuple[SelectedMailbox, Iterable[UntaggedResponse]]:
        """Compares the state of the current object to that of the last fork,
        returning the untagged responses that reflect any changes. A new copy
        of the object is also returned, ready for the next command.

        Args:
            command: The command that was finished.

        """
        frozen = _Frozen(self)
        cls = type(self)
        copy = cls(self._mailbox_id, self._readonly, self._permanent_flags,
                   self._session_flags, self._selected_set, self._lookup,
                   _mod_sequence=self._mod_sequence,
                   _prev=frozen, _messages=self._messages)
        if self._prev is not None:
            with_uid: bool = getattr(command, 'uid', False)
            untagged = self._compare(self._prev, frozen, with_uid)
        else:
            untagged = []
        return copy, untagged

    def _compare(self, before: _Frozen, after: _Frozen,
                 with_uid: bool) -> Iterable[UntaggedResponse]:
        if after.is_deleted:
            yield ResponseBye(b'Selected mailbox no longer exists.')
            return
        cache = self._messages._cache
        session_flags = self._session_flags
        expunged_uids = before.uids - after.uids
        new_uids = after.uids - before.uids
        if not self._hide_expunged and expunged_uids:
            for uid in sorted(expunged_uids, reverse=True):
                yield ExpungeResponse(before.seqs_cache[uid])
        if new_uids:
            yield ExistsResponse(len(after.uids))
        if len(after.recent) != len(before.recent):
            yield RecentResponse(len(after.recent))
        new_recent = (after.recent - before.recent)
        new_flags = (after.flags - before.flags - self._silenced_flags)
        new_sflags = (after.sflags - before.sflags - self._silenced_sflags)
        fetch_uids = chain(new_recent,
                           (uid for uid, _ in new_flags),
                           (uid for uid, _ in new_sflags))
        for uid, _ in groupby(sorted(fetch_uids)):
            seq = after.seqs_cache[uid]
            msg_flags = cache[uid].get_flags(session_flags)
            fetch_data: list[FetchValue] = [
                FetchValue.of(_flags_attr, List(msg_flags, sort=True))]
            if with_uid:
                fetch_data.append(FetchValue.of(_uid_attr, Number(uid)))
            yield FetchResponse(seq, fetch_data)
