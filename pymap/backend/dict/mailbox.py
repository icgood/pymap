
from __future__ import annotations

import hashlib
from bisect import bisect_left
from collections.abc import Iterable, Sequence, AsyncIterable
from datetime import datetime
from itertools import islice
from typing import Optional
from weakref import finalize, WeakKeyDictionary, WeakValueDictionary

from pymap.bytes import HashStream
from pymap.concurrent import Event, ReadWriteLock
from pymap.context import subsystem
from pymap.flags import FlagOp
from pymap.interfaces.message import CachedMessage
from pymap.listtree import ListTree
from pymap.mailbox import MailboxSnapshot
from pymap.message import BaseMessage, BaseLoadedMessage
from pymap.mime import MessageContent
from pymap.parsing.message import AppendMessage
from pymap.parsing.specials import ObjectId, FetchRequirement
from pymap.parsing.specials.flag import Flag, Seen
from pymap.selected import SelectedSet, SelectedMailbox
from pymap.threads import ThreadKey

from ..mailbox import MailboxDataInterface, MailboxSetInterface

__all__ = ['Message', 'MailboxData', 'MailboxSet']


class Message(BaseMessage):

    __slots__ = ['_recent', '_content']

    def __init__(self, uid: int, internal_date: datetime,
                 permanent_flags: Iterable[Flag], *, expunged: bool = False,
                 email_id: ObjectId = None, thread_id: ObjectId = None,
                 recent: bool = False, content: MessageContent = None) -> None:
        super().__init__(uid, internal_date, permanent_flags,
                         expunged=expunged, email_id=email_id,
                         thread_id=thread_id)
        self._recent = recent
        self._content = content

    @classmethod
    def copy(cls, msg: Message, *, uid: int = None, recent: bool = False,
             expunged: bool = False) -> Message:
        if uid is None:
            uid = msg.uid
        return cls(uid, msg.internal_date, msg.permanent_flags,
                   expunged=expunged, email_id=msg.email_id,
                   thread_id=msg.thread_id, recent=recent,
                   content=msg._content)

    @property
    def recent(self) -> bool:
        return self._recent

    @recent.setter
    def recent(self, recent: bool) -> None:
        self._recent = recent

    async def load_content(self, requirement: FetchRequirement) \
            -> LoadedMessage:
        return LoadedMessage(self, requirement, self._content)


class LoadedMessage(BaseLoadedMessage):
    pass


class _ModSequenceMapping:

    def __init__(self) -> None:
        super().__init__()
        self._highest = 0
        self._uids: dict[int, int] = {}
        self._updates: dict[int, set[int]] = {}
        self._expunges: dict[int, set[int]] = {}
        self._mod_seqs_order: list[int] = []

    @property
    def highest(self) -> int:
        return self._highest

    def _remove_prev(self, uid: int, prev_mod_seq: int,
                     data: dict[int, set[int]]) -> None:
        uid_set = data.get(prev_mod_seq, None)
        if uid_set is not None:
            uid_set.discard(uid)
            if not uid_set:
                del data[prev_mod_seq]
                self._mod_seqs_order.remove(prev_mod_seq)

    def _set(self, uids: Iterable[int], data: dict[int, set[int]]) -> None:
        self._highest = mod_seq = self._highest + 1
        self._mod_seqs_order.append(mod_seq)
        new_uid_set = data.setdefault(mod_seq, set())
        new_uid_set.update(uids)
        for uid in uids:
            prev_mod_seq = self._uids.get(uid, None)
            self._uids[uid] = mod_seq
            if prev_mod_seq is not None:
                self._remove_prev(uid, prev_mod_seq, self._updates)
                self._remove_prev(uid, prev_mod_seq, self._expunges)

    def update(self, uids: Iterable[int]) -> None:
        return self._set(uids, self._updates)

    def expunge(self, uids: Iterable[int]) -> None:
        return self._set(uids, self._expunges)

    def find_updated(self, mod_seq: int) \
            -> tuple[frozenset[int], frozenset[int]]:
        updates_ret: set[int] = set()
        expunges_ret: set[int] = set()
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
        return frozenset(updates_ret), frozenset(expunges_ret)


class _ContentCache:

    def __init__(self) -> None:
        super().__init__()
        self._email_ids: dict[bytes, ObjectId] = {}
        self._hashes: dict[ObjectId, bytes] = {}
        self._content: WeakValueDictionary[ObjectId, MessageContent] = \
            WeakValueDictionary()

    def add(self, content: MessageContent) -> ObjectId:
        msg_hash = HashStream(hashlib.sha1()).digest(content)
        existing = self._email_ids.get(msg_hash)
        if existing is not None:
            return existing
        email_id = ObjectId.random_email_id()
        self._email_ids[msg_hash] = email_id
        self._hashes[email_id] = msg_hash
        self._content[email_id] = content
        finalize(content, self._remove, msg_hash, email_id)
        return email_id

    def _remove(self, msg_hash: bytes, email_id: ObjectId) -> None:
        self._email_ids.pop(msg_hash, None)
        self._hashes.pop(email_id, None)

    def get(self, email_id: ObjectId) -> MessageContent:
        return self._content[email_id]


class _ThreadCache:

    def __init__(self) -> None:
        super().__init__()
        self._thread_ids: WeakKeyDictionary[ThreadKey, ObjectId] = \
            WeakKeyDictionary()
        self._ref: WeakKeyDictionary[MessageContent, Sequence[ThreadKey]] = \
            WeakKeyDictionary()

    def add(self, content: MessageContent) -> ObjectId:
        self._ref[content] = thread_keys = ThreadKey.get_all(content.header)
        for thread_key in thread_keys:
            thread_id = self._thread_ids.get(thread_key)
            if thread_id is not None:
                break
        else:
            thread_id = ObjectId.random_thread_id()
        for thread_key in thread_keys:
            self._thread_ids.setdefault(thread_key, thread_id)
        return thread_id


class MailboxData(MailboxDataInterface[Message]):
    """Implementation of :class:`~pymap.backend.mailbox.MailboxDataInterface`
    for the dict backend.

    """

    def __init__(self, content_cache: _ContentCache,
                 thread_cache: _ThreadCache) -> None:
        self._mailbox_id = ObjectId.random_mailbox_id()
        self._content_cache = content_cache
        self._thread_cache = thread_cache
        self._readonly = False
        self._updated = subsystem.get().new_event()
        self._messages_lock = subsystem.get().new_rwlock()
        self._selected_set = SelectedSet()
        self._uid_validity = MailboxSnapshot.new_uid_validity()
        self._max_uid = 100
        self._mod_sequences = _ModSequenceMapping()
        self._messages: dict[int, Message] = {}

    @property
    def mailbox_id(self) -> ObjectId:
        return self._mailbox_id

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

    async def update_selected(self, selected: SelectedMailbox, *,
                              wait_on: Event = None) -> SelectedMailbox:
        if wait_on is not None:
            either_event = wait_on.or_event(self._updated)
            await either_event.wait()
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

    async def append(self, append_msg: AppendMessage, *,
                     recent: bool = False) -> Message:
        when = append_msg.when or datetime.now()
        content = MessageContent.parse(append_msg.literal)
        email_id = self._content_cache.add(content)
        thread_id = self._thread_cache.add(content)
        async with self.messages_lock.write_lock():
            self._max_uid = new_uid = self._max_uid + 1
            message = Message(new_uid, when, append_msg.flag_set,
                              email_id=email_id, thread_id=thread_id,
                              recent=recent, content=content)
            self._messages[new_uid] = message
            self._mod_sequences.update([new_uid])
            self._updated.set()
            return message

    async def copy(self, uid: int, destination: MailboxData, *,
                   recent: bool = False) -> Optional[int]:
        async with self.messages_lock.read_lock():
            try:
                message = self._messages[uid]
            except KeyError:
                return None
        async with destination.messages_lock.write_lock():
            destination._max_uid = dest_uid = destination._max_uid + 1
            new_msg = Message.copy(message, uid=dest_uid, recent=recent)
            destination._messages[dest_uid] = new_msg
            destination._mod_sequences.update([dest_uid])
            destination._updated.set()
        return dest_uid

    async def move(self, uid: int, destination: MailboxData, *,
                   recent: bool = False) -> Optional[int]:
        async with self.messages_lock.write_lock():
            try:
                message = self._messages.pop(uid)
            except KeyError:
                return None
            self._mod_sequences.expunge([uid])
            self._updated.set()
        async with destination.messages_lock.write_lock():
            destination._max_uid = dest_uid = destination._max_uid + 1
            new_msg = Message.copy(message, uid=dest_uid, recent=recent)
            destination._messages[dest_uid] = new_msg
            destination._mod_sequences.update([dest_uid])
            destination._updated.set()
        return dest_uid

    async def get(self, uid: int, cached_msg: CachedMessage) -> Message:
        if uid < 1 or uid > self._max_uid:
            raise IndexError(uid)
        async with self.messages_lock.read_lock():
            msg = self._messages.get(uid)
        if msg is None:
            if not isinstance(cached_msg, Message):
                raise TypeError(cached_msg)
            msg = Message.copy(cached_msg, expunged=True)
        return msg

    async def update(self, uid: int, cached_msg: CachedMessage,
                     flag_set: frozenset[Flag], mode: FlagOp) -> Message:
        msg = await self.get(uid, cached_msg)
        msg.permanent_flags = mode.apply(msg.permanent_flags, flag_set)
        self._mod_sequences.update([uid])
        self._updated.set()
        return msg

    async def delete(self, uids: Iterable[int]) -> None:
        async with self.messages_lock.write_lock():
            for uid in uids:
                try:
                    del self._messages[uid]
                except KeyError:
                    pass
            self._mod_sequences.expunge(uids)
            self._updated.set()

    async def claim_recent(self, selected: SelectedMailbox) -> None:
        uids: list[int] = []
        async for msg in self.messages():
            if msg.recent:
                msg.recent = False
                msg_uid = msg.uid
                selected.session_flags.add_recent(msg_uid)
                uids.append(msg_uid)
        self._mod_sequences.update(uids)
        self._updated.set()

    async def cleanup(self) -> None:
        pass

    async def messages(self) -> AsyncIterable[Message]:
        async with self.messages_lock.read_lock():
            for msg in self._messages.values():
                yield msg

    async def snapshot(self) -> MailboxSnapshot:
        exists = 0
        recent = 0
        unseen = 0
        first_unseen: Optional[int] = None
        next_uid = self._max_uid + 1
        async for msg in self.messages():
            exists += 1
            if msg.recent:
                recent += 1
            if Seen not in msg.permanent_flags:
                unseen += 1
                if first_unseen is None:
                    first_unseen = exists
        return MailboxSnapshot(self.mailbox_id, self.readonly,
                               self.uid_validity, self.permanent_flags,
                               self.session_flags, exists, recent, unseen,
                               first_unseen, next_uid)


class MailboxSet(MailboxSetInterface[MailboxData]):
    """Implementation of :class:`~pymap.backend.mailbox.MailboxSetInterface`
    for the dict backend.

    """

    def __init__(self) -> None:
        super().__init__()
        self._content_cache = _ContentCache()
        self._thread_cache = _ThreadCache()
        self._inbox = MailboxData(self._content_cache, self._thread_cache)
        self._set: dict[str, MailboxData] = {}
        self._set_lock = subsystem.get().new_rwlock()
        self._subscribed: dict[str, bool] = {}

    @property
    def delimiter(self) -> str:
        return '/'

    async def set_subscribed(self, name: str, subscribed: bool) -> None:
        async with self._set_lock.write_lock():
            self._subscribed[name] = subscribed

    async def list_subscribed(self) -> ListTree:
        async with self._set_lock.read_lock():
            mailboxes = [child for child in self._set.keys()
                         if self._subscribed.get(child)]
        return ListTree(self.delimiter).update('INBOX', *mailboxes)

    async def list_mailboxes(self) -> ListTree:
        async with self._set_lock.read_lock():
            mailboxes = list(self._set.keys())
        return ListTree(self.delimiter).update('INBOX', *mailboxes)

    async def get_mailbox(self, name: str) -> MailboxData:
        if name.upper() == 'INBOX':
            return self._inbox
        async with self._set_lock.read_lock():
            return self._set[name]

    async def add_mailbox(self, name: str) -> ObjectId:
        async with self._set_lock.read_lock():
            if name in self._set:
                raise ValueError(name)
        async with self._set_lock.write_lock():
            self._set[name] = mbx = MailboxData(
                self._content_cache, self._thread_cache)
            return mbx.mailbox_id

    async def delete_mailbox(self, name: str) -> None:
        async with self._set_lock.read_lock():
            if name not in self._set:
                raise KeyError(name)
        async with self._set_lock.write_lock():
            del self._set[name]

    async def rename_mailbox(self, before: str, after: str) -> None:
        async with self._set_lock.read_lock():
            tree = ListTree(self.delimiter).update('INBOX', *self._set.keys())
            before_entry = tree.get(before)
            after_entry = tree.get(after)
            if before_entry is None:
                raise KeyError(before)
            elif after_entry is not None:
                raise ValueError(after)
        async with self._set_lock.write_lock():
            for before_name, after_name in tree.get_renames(before, after):
                if before_name == 'INBOX':
                    self._set[after_name] = self._inbox
                    self._inbox = MailboxData(
                        self._content_cache, self._thread_cache)
                else:
                    self._set[after_name] = self._set[before_name]
                    del self._set[before_name]
