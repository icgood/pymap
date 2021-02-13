
from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime
from typing import Optional

import msgpack
from aioredis import Redis, ReplyError, MultiExecError

from pymap.bytes import HashStream
from pymap.concurrent import Event
from pymap.exceptions import MailboxNotFound, MailboxConflict, TemporaryFailure
from pymap.flags import FlagOp
from pymap.interfaces.message import CachedMessage
from pymap.listtree import ListTree
from pymap.mailbox import MailboxSnapshot
from pymap.mime import MessageContent
from pymap.parsing.message import AppendMessage
from pymap.parsing.modutf7 import modutf7_encode, modutf7_decode
from pymap.parsing.specials import ObjectId, SequenceSet
from pymap.parsing.specials.flag import Flag
from pymap.selected import SelectedSet, SelectedMailbox
from pymap.threads import ThreadKey

from .keys import CleanupKeys, NamespaceKeys, ContentKeys, MailboxKeys
from .message import Message
from .scripts.mailbox import MailboxScripts
from .scripts.namespace import NamespaceScripts
from ..mailbox import MailboxDataInterface, MailboxSetInterface

__all__ = ['Message', 'MailboxData', 'MailboxSet']

_scripts = MailboxScripts()
_ns_scripts = NamespaceScripts()

_ChangesRaw = Sequence[tuple[bytes, Mapping[bytes, bytes]]]


class MailboxData(MailboxDataInterface[Message]):
    """Implementation of :class:`~pymap.backend.mailbox.MailboxDataInterface`
    for the redis backend.

    """

    def __init__(self, redis: Redis, mailbox_id: bytes, uid_validity: int,
                 keys: MailboxKeys, ns_keys: NamespaceKeys,
                 cl_keys: CleanupKeys) -> None:
        super().__init__()
        self._redis = redis
        self._mailbox_id = ObjectId(mailbox_id)
        self._uid_validity = uid_validity
        self._selected_set = SelectedSet()
        self._keys = keys
        self._ns_keys = ns_keys
        self._cl_keys = cl_keys

    @property
    def mailbox_id(self) -> ObjectId:
        return self._mailbox_id

    @property
    def readonly(self) -> bool:
        return False

    @property
    def uid_validity(self) -> int:
        return self._uid_validity

    @property
    def selected_set(self) -> SelectedSet:
        return self._selected_set

    def _get_msg(self, uid: int, msg_raw: bytes) -> Message:
        msg = msgpack.unpackb(msg_raw, raw=True)
        msg_flags = {Flag(flag) for flag in msg[b'flags']}
        msg_email_id = ObjectId.maybe(msg[b'email_id'])
        msg_thread_id = ObjectId.maybe(msg[b'thread_id'])
        msg_time = datetime.fromisoformat(msg[b'date'].decode('ascii'))
        return Message(uid, msg_time, msg_flags,
                       email_id=msg_email_id, thread_id=msg_thread_id,
                       redis=self._redis, ns_keys=self._ns_keys)

    async def update_selected(self, selected: SelectedMailbox, *,
                              wait_on: Event = None) -> SelectedMailbox:
        last_mod_seq = selected.mod_sequence
        if wait_on is not None:
            await self._wait_updates(selected, last_mod_seq)
        if last_mod_seq is None:
            await self._load_initial(selected)
        else:
            await self._load_updates(selected, last_mod_seq)
        return selected

    async def append(self, append_msg: AppendMessage, *,
                     recent: bool = False) -> Message:
        redis = self._redis
        keys = self._keys
        ns_keys = self._ns_keys
        when = append_msg.when or datetime.now()
        content = MessageContent.parse(append_msg.literal)
        content_hash = HashStream(hashlib.sha1()).digest(content)
        new_email_id = ObjectId.new_email_id(content_hash)
        ct_keys = ContentKeys(ns_keys, new_email_id)
        new_uid, email_id, thread_id = await _scripts.add(
            redis, ns_keys, ct_keys, keys,
            recent=recent, flags=[str(flag) for flag in append_msg.flag_set],
            date=when.isoformat().encode('ascii'),
            email_id=new_email_id.value,
            thread_id=ObjectId.random_thread_id().value,
            thread_keys=['\0'.join(thread_key) for thread_key in
                         ThreadKey.get_all(content.header)],
            message=append_msg.literal, message_json=content.json,
            header=bytes(content.header), header_json=content.header.json)
        return Message(new_uid, when, append_msg.flag_set,
                       email_id=ObjectId(email_id),
                       thread_id=ObjectId(thread_id),
                       redis=redis, ns_keys=ns_keys)

    async def copy(self, uid: int, destination: MailboxData, *,
                   recent: bool = False) -> Optional[int]:
        redis = self._redis
        keys = self._keys
        ns_keys = self._ns_keys
        dest_keys = destination._keys
        try:
            dest_uid = await _scripts.copy(redis, ns_keys, keys, dest_keys,
                                           source_uid=uid, recent=recent)
        except ReplyError as exc:
            if 'message not found' in str(exc):
                return None
            raise
        return dest_uid

    async def move(self, uid: int, destination: MailboxData, *,
                   recent: bool = False) -> Optional[int]:
        redis = self._redis
        keys = self._keys
        ns_keys = self._ns_keys
        dest_keys = destination._keys
        try:
            dest_uid = await _scripts.move(redis, ns_keys, keys, dest_keys,
                                           source_uid=uid, recent=recent)
        except ReplyError as exc:
            if 'message not found' in str(exc):
                return None
            raise
        return dest_uid

    async def get(self, uid: int, cached_msg: CachedMessage) -> Message:
        redis = self._redis
        keys = self._keys
        message_raw = await redis.hget(keys.uids, uid)
        if message_raw is None:
            if not isinstance(cached_msg, Message):
                raise TypeError(cached_msg)
            return Message.copy_expunged(cached_msg)
        return self._get_msg(uid, message_raw)

    async def update(self, uid: int, cached_msg: CachedMessage,
                     flag_set: frozenset[Flag], mode: FlagOp) -> Message:
        keys = self._keys
        ns_keys = self._ns_keys
        try:
            message_raw = await _scripts.update(
                self._redis, ns_keys, keys, uid=uid, mode=bytes(mode),
                flags=[str(flag) for flag in flag_set])
        except ReplyError as exc:
            if 'message not found' not in str(exc):
                raise
            if not isinstance(cached_msg, Message):
                raise TypeError(cached_msg)
            return Message.copy_expunged(cached_msg)
        return self._get_msg(uid, message_raw)

    async def delete(self, uids: Iterable[int]) -> None:
        keys = self._keys
        ns_keys = self._ns_keys
        uids = list(uids)
        if not uids:
            return
        await _scripts.delete(self._redis, ns_keys, keys, self._cl_keys,
                              uids=uids)

    async def claim_recent(self, selected: SelectedMailbox) -> None:
        keys = self._keys
        multi = self._redis.multi_exec()
        multi.smembers(keys.recent)
        multi.unlink(keys.recent)
        recent, _ = await multi.execute()
        for uid_bytes in recent:
            selected.session_flags.add_recent(int(uid_bytes))

    async def find_deleted(self, seq_set: SequenceSet,
                           selected: SelectedMailbox) -> Sequence[int]:
        if not seq_set.is_all:
            return await super().find_deleted(seq_set, selected)
        deleted = await self._redis.smembers(self._keys.deleted)
        return [int(uid) for uid in deleted]

    async def cleanup(self) -> None:
        pass

    async def snapshot(self) -> MailboxSnapshot:
        next_uid, num_exists, num_recent, num_unseen, first_unseen = \
            await _scripts.snapshot(self._redis, self._keys)
        return MailboxSnapshot(self.mailbox_id, self.readonly,
                               self.uid_validity, self.permanent_flags,
                               self.session_flags, num_exists, num_recent,
                               num_unseen, first_unseen, next_uid)

    def _get_mod_seq(self, changes: _ChangesRaw) -> Optional[bytes]:
        try:
            ret = changes[-1][0]
        except IndexError:
            return None
        else:
            left, right = ret.rsplit(b'-', 1)
            next_right = int(right) + 1
            return b'%b-%i' % (left, next_right)

    async def _load_initial(self, selected: SelectedMailbox) -> None:
        keys = self._keys
        multi = self._redis.multi_exec()
        multi.hgetall(keys.uids)
        multi.xrevrange(keys.changes, count=1)
        msg_raw_map, last_changes = await multi.execute()
        messages = [self._get_msg(int(uid), msg_raw)
                    for uid, msg_raw in msg_raw_map.items()]
        selected.mod_sequence = self._get_mod_seq(last_changes)
        selected.set_messages(messages)

    def _get_changes(self, changes: _ChangesRaw) \
            -> tuple[Sequence[Message], frozenset[int]]:
        expunged = frozenset(int(fields[b'uid']) for _, fields in changes
                             if fields[b'type'] == b'expunge')
        messages: list[Message] = []
        for _, fields in changes:
            uid = int(fields[b'uid'])
            if fields[b'type'] != b'fetch' or uid in expunged:
                continue
            msg = self._get_msg(uid, fields[b'message'])
            messages.append(msg)
        return messages, expunged

    async def _load_updates(self, selected: SelectedMailbox,
                            last_mod_seq: bytes) -> None:
        keys = self._keys
        multi = self._redis.multi_exec()
        multi.xlen(keys.changes)
        multi.xrange(keys.changes, start=last_mod_seq)
        multi.xrevrange(keys.changes, count=1)
        changes_len, changes, last_changes = await multi.execute()
        if len(changes) == changes_len:
            return await self._load_initial(selected)
        messages, expunged = self._get_changes(changes)
        selected.mod_sequence = self._get_mod_seq(last_changes)
        selected.add_updates(messages, expunged)

    async def _wait_updates(self, selected: SelectedMailbox,
                            last_mod_seq: bytes) -> None:
        keys = self._keys
        redis = self._redis
        await redis.xread([keys.changes], latest_ids=[last_mod_seq],
                          timeout=1000, count=1)


class MailboxSet(MailboxSetInterface[MailboxData]):
    """Implementation of :class:`~pymap.backend.mailbox.MailboxSetInterface`
    for the redis backend.

    """

    def __init__(self, redis: Redis, keys: NamespaceKeys,
                 cl_keys: CleanupKeys) -> None:
        super().__init__()
        self._redis = redis
        self._keys = keys
        self._cl_keys = cl_keys

    @property
    def delimiter(self) -> str:
        return '/'

    async def set_subscribed(self, name: str, subscribed: bool) -> None:
        pipe = self._redis.pipeline()
        pipe.unwatch()
        if subscribed:
            pipe.sadd(self._keys.subscribed, name)
        else:
            pipe.srem(self._keys.subscribed, name)
        await pipe.execute()

    async def list_subscribed(self) -> ListTree:
        pipe = self._redis.pipeline()
        pipe.unwatch()
        pipe.smembers(self._keys.subscribed)
        _, mailboxes = await pipe.execute()
        return ListTree(self.delimiter).update('INBOX', *(
            modutf7_decode(name) for name in mailboxes))

    async def list_mailboxes(self) -> ListTree:
        mailboxes = await _ns_scripts.list(self._redis, self._keys)
        return ListTree(self.delimiter).update('INBOX', *(
            modutf7_decode(name) for name in mailboxes))

    async def get_mailbox(self, name: str) -> MailboxData:
        redis = self._redis
        name_key = modutf7_encode(name)
        try:
            mbx_id, uid_val = await _ns_scripts.get(
                redis, self._keys, name=name_key)
        except ReplyError as exc:
            if 'mailbox not found' in str(exc):
                raise KeyError(name_key) from exc
            raise
        mbx_keys = MailboxKeys(self._keys, mbx_id)
        return MailboxData(redis, mbx_id, uid_val, mbx_keys, self._keys,
                           self._cl_keys)

    async def add_mailbox(self, name: str) -> ObjectId:
        name_key = modutf7_encode(name)
        mbx_id = ObjectId.random_mailbox_id()
        try:
            await _ns_scripts.add(self._redis, self._keys,
                                  name=name_key,
                                  mailbox_id=mbx_id.value)
        except ReplyError as exc:
            if 'mailbox already exists' in str(exc):
                raise ValueError(name_key) from exc
            raise
        return mbx_id

    async def delete_mailbox(self, name: str) -> None:
        name_key = modutf7_encode(name)
        try:
            await _ns_scripts.delete(self._redis, self._keys, self._cl_keys,
                                     name=name_key)
        except ReplyError as exc:
            if 'mailbox not found' in str(exc):
                raise KeyError(name_key) from exc
            raise

    async def rename_mailbox(self, before: str, after: str) -> None:
        redis = self._redis
        pipe = redis.pipeline()
        pipe.unwatch()
        pipe.watch(self._keys.mailboxes)
        pipe.hgetall(self._keys.mailboxes)
        _, _, all_keys = await pipe.execute()
        all_mbx = {modutf7_decode(key): ns for key, ns in all_keys.items()}
        tree = ListTree(self.delimiter).update('INBOX', *all_mbx.keys())
        before_entry = tree.get(before)
        after_entry = tree.get(after)
        if before_entry is None:
            raise MailboxNotFound(before)
        elif after_entry is not None:
            raise MailboxConflict(after)
        multi = redis.multi_exec()
        for before_name, after_name in tree.get_renames(before, after):
            before_id = all_mbx[before_name]
            before_key = modutf7_encode(before_name)
            after_key = modutf7_encode(after_name)
            multi.hset(self._keys.mailboxes, after_key, before_id)
            multi.hdel(self._keys.mailboxes, before_key)
            multi.hincrby(self._keys.uid_validity, after_key)
        if before == 'INBOX':
            inbox_id = ObjectId.random_mailbox_id()
            multi.hset(self._keys.mailboxes, b'INBOX', inbox_id.value)
            multi.hincrby(self._keys.uid_validity, b'INBOX')
        try:
            await multi.execute()
        except MultiExecError as exc:
            msg = 'Mailboxes changed externally, please try again.'
            raise TemporaryFailure(msg) from exc
