
from bisect import bisect_left
from collections import OrderedDict
from itertools import islice
from typing import Tuple, Sequence, Dict, Optional, Iterable, AsyncIterable, \
    List, Set, AbstractSet

from pymap.concurrent import ReadWriteLock
from pymap.context import subsystem
from pymap.exceptions import MailboxNotFound, MailboxConflict
from pymap.interfaces.message import AppendMessage, CachedMessage
from pymap.mailbox import MailboxSnapshot
from pymap.parsing.specials import FetchRequirement
from pymap.selected import SelectedSet, SelectedMailbox

from ..mailbox import Message, MailboxDataInterface, MailboxSetInterface

__all__ = ['Message', 'MailboxData', 'MailboxSet']


class _ModSequenceMapping:

    def __init__(self) -> None:
        super().__init__()
        self._highest = 0
        self._uids: Dict[int, int] = {}
        self._updates: Dict[int, Set[int]] = {}
        self._expunges: Dict[int, Set[int]] = {}
        self._mod_seqs_order: List[int] = []

    @property
    def highest(self) -> int:
        return self._highest

    def _set(self, uids: Iterable[int], data: Dict[int, Set[int]]) -> None:
        self._highest = mod_seq = self._highest + 1
        self._mod_seqs_order.append(mod_seq)
        new_uid_set = data.setdefault(mod_seq, set())
        new_uid_set.update(uids)
        for uid in uids:
            prev_mod_seq = self._uids.get(uid, None)
            self._uids[uid] = mod_seq
            if prev_mod_seq is not None:
                uid_set = self._updates[prev_mod_seq]
                uid_set.discard(uid)
                if not uid_set:
                    del self._updates[prev_mod_seq]
                    self._mod_seqs_order.remove(prev_mod_seq)

    def update(self, uids: Iterable[int]) -> None:
        return self._set(uids, self._updates)

    def expunge(self, uids: Iterable[int]) -> None:
        return self._set(uids, self._expunges)

    def find_updated(self, mod_seq: int) \
            -> Tuple[AbstractSet[int], AbstractSet[int]]:
        updates_ret: Set[int] = set()
        expunges_ret: Set[int] = set()
        updates = self._updates
        expunges = self._expunges
        mod_seqs_order = self._mod_seqs_order
        mod_seqs_len = len(mod_seqs_order)
        idx = bisect_left(mod_seqs_order, mod_seq, 0, mod_seqs_len)
        for newer_mod_seq in islice(mod_seqs_order, idx, mod_seqs_len):
            updates_set = updates.get(newer_mod_seq)
            expunges_set = expunges.get(newer_mod_seq)
            if updates_set is not None:
                updates_ret.update(updates_set)
            if expunges_set is not None:
                expunges_ret.update(expunges_set)
        return updates_ret, expunges_ret


class MailboxData(MailboxDataInterface[Message]):
    """Implementation of :class:`~pymap.backend.mailbox.MailboxDataInterface`
    for the dict backend.

    """

    def __init__(self, name: str) -> None:
        self._name = name
        self._readonly = False
        self._messages_lock = subsystem.get().new_rwlock()
        self._selected_set = SelectedSet()
        self._reset_messages()

    def _reset_messages(self) -> None:
        self._uid_validity = MailboxSnapshot.new_uid_validity()
        self._max_uid = 100
        self._mod_sequences = _ModSequenceMapping()
        self._messages: Dict[int, Message] = OrderedDict()

    @property
    def name(self) -> str:
        return self._name

    @property
    def readonly(self) -> bool:
        return self._readonly

    @property
    def uid_validity(self) -> int:
        return self._uid_validity

    @property
    def messages_lock(self) -> ReadWriteLock:
        return self._messages_lock

    @property
    def selected_set(self) -> SelectedSet:
        return self._selected_set

    async def get_next_uid(self) -> int:
        return self._max_uid + 1

    async def update_selected(self, selected: SelectedMailbox) \
            -> SelectedMailbox:
        selected.uid_validity = self.uid_validity
        mod_sequence = selected.mod_sequence
        selected.mod_sequence = self._mod_sequences.highest
        if mod_sequence is None:
            all_messages = list(self._messages.values())
            selected.add_updates(all_messages, [])
        else:
            updated, expunged = self._mod_sequences.find_updated(mod_sequence)
            updated_messages = [self._messages[uid] for uid in updated
                                if uid in self._messages]
            selected.add_updates(updated_messages, expunged)
        return selected

    async def add(self, append_msg: AppendMessage, recent: bool = False) \
            -> Message:
        async with self.messages_lock.write_lock():
            self._max_uid = new_uid = self._max_uid + 1
            message = Message.parse(new_uid, append_msg.message,
                                    append_msg.flag_set, append_msg.when,
                                    recent=recent)
            self._messages[new_uid] = message
            self._mod_sequences.update([new_uid])
            return message

    async def get(self, uid: int, cached_msg: CachedMessage = None,
                  requirement: FetchRequirement = FetchRequirement.METADATA) \
            -> Optional[Message]:
        if uid < 1 or uid > self._max_uid:
            raise IndexError(uid)
        async with self.messages_lock.read_lock():
            ret = self._messages.get(uid)
            if ret is None and cached_msg is not None:
                return Message(cached_msg.uid, cached_msg.get_flags(),
                               cached_msg.internal_date, expunged=True)
            else:
                return ret

    async def delete(self, uids: Iterable[int]) -> None:
        async with self.messages_lock.write_lock():
            for uid in uids:
                try:
                    del self._messages[uid]
                except KeyError:
                    pass
        self._mod_sequences.expunge(uids)

    async def claim_recent(self, selected: SelectedMailbox) -> None:
        uids: List[int] = []
        async for msg in self.messages():
            if msg.recent:
                msg.recent = False
                msg_uid = msg.uid
                selected.session_flags.add_recent(msg_uid)
                uids.append(msg_uid)
        self._mod_sequences.update(uids)

    async def save_flags(self, messages: Iterable[Message]) -> None:
        self._mod_sequences.update(msg.uid for msg in messages)

    async def cleanup(self) -> None:
        pass

    async def uids(self) -> AsyncIterable[int]:
        async with self.messages_lock.read_lock():
            for key in self._messages.keys():
                yield key

    async def messages(self) -> AsyncIterable[Message]:
        async with self.messages_lock.read_lock():
            for msg in self._messages.values():
                yield msg

    async def items(self) -> AsyncIterable[Tuple[int, Message]]:
        async with self.messages_lock.read_lock():
            for key, msg in self._messages.items():
                yield (key, msg)


class MailboxSet(MailboxSetInterface[MailboxData]):
    """Implementation of :class:`~pymap.backend.mailbox.MailboxSetInterface`
    for the dict backend.

    """

    def __init__(self) -> None:
        super().__init__()
        self._inbox = MailboxData('INBOX')
        self._set: Dict[str, 'MailboxData'] = OrderedDict()
        self._set_lock = subsystem.get().new_rwlock()
        self._subscribed: Dict[str, bool] = {}

    @property
    def delimiter(self) -> str:
        return '.'

    async def set_subscribed(self, name: str, subscribed: bool) -> None:
        async with self._set_lock.write_lock():
            self._subscribed[name] = subscribed

    async def list_subscribed(self) -> Sequence[str]:
        async with self._set_lock.read_lock():
            return [child for child in self._set.keys()
                    if self._subscribed.get(child)]

    async def list_mailboxes(self) -> Sequence[str]:
        async with self._set_lock.read_lock():
            return list(self._set.keys())

    async def get_mailbox(self, name: str,
                          try_create: bool = False) -> 'MailboxData':
        if name.upper() == 'INBOX':
            return self._inbox
        async with self._set_lock.read_lock():
            if name not in self._set:
                raise MailboxNotFound(name, try_create)
            return self._set[name]

    async def add_mailbox(self, name: str) -> 'MailboxData':
        async with self._set_lock.read_lock():
            if name in self._set:
                raise MailboxConflict(name)
        async with self._set_lock.write_lock():
            self._set[name] = ret = MailboxData(name)
        return ret

    async def delete_mailbox(self, name: str) -> None:
        async with self._set_lock.read_lock():
            if name not in self._set:
                raise MailboxNotFound(name)
        async with self._set_lock.write_lock():
            del self._set[name]

    async def rename_mailbox(self, before: str, after: str) -> 'MailboxData':
        async with self._set_lock.read_lock():
            if before != 'INBOX' and before not in self._set:
                raise MailboxNotFound(before)
            elif after in self._set:
                raise MailboxConflict(after)
        if before == 'INBOX':
            async with self._set_lock.write_lock():
                self._set[after] = ret = MailboxData(after)
                ret._uid_validity = self._inbox._uid_validity
                ret._max_uid = self._inbox._max_uid
                ret._messages = self._inbox._messages
                self._inbox._reset_messages()
                return ret
        else:
            async with self._set_lock.write_lock():
                self._set[after] = self._set[before]
                del self._set[before]
                return self._set[after]
