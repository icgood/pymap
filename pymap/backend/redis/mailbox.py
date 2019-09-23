
from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Optional, Sequence, List, Tuple, FrozenSet, Iterable

from aioredis import Redis, ReplyError, MultiExecError  # type: ignore

from pymap.bytes import HashStream
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

from ._util import WatchMultiExec
from .keys import CleanupKeys, NamespaceKeys, ContentKeys, MailboxKeys, \
    MessageKeys
from .message import Message
from .scripts.mailbox import MailboxScripts, MailboxSetScripts
from ..mailbox import MailboxDataInterface, MailboxSetInterface

__all__ = ['Message', 'MailboxData', 'MailboxSet']

_scripts = MailboxScripts()
_set_scripts = MailboxSetScripts()


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

    async def update_selected(self, selected: SelectedMailbox) \
            -> SelectedMailbox:
        last_mod_seq = selected.mod_sequence
        if last_mod_seq is None:
            mod_seq, updated, expunged = await self._get_initial()
        else:
            mod_seq, updated, expunged = await self._get_updated(last_mod_seq)
        selected.mod_sequence = mod_seq
        selected.add_updates(updated, expunged)
        return selected

    async def append(self, append_msg: AppendMessage, *,
                     recent: bool = False) -> Message:
        redis = self._redis
        keys = self._keys
        ns_keys = self._ns_keys
        content = MessageContent.parse(append_msg.literal)
        new_uid, email_id, thread_id, send_content = await _scripts.prepare(
            redis, ns_keys, keys,
            new_email_id=ObjectId.random_email_id().value,
            new_thread_id=ObjectId.random_thread_id().value,
            content_hash=HashStream(hashlib.sha1()).digest(content),
            thread_keys=['\0'.join(thread_key) for thread_key in
                         ThreadKey.get_all(content.header)])
        when = append_msg.when or datetime.now()
        ct_keys = ContentKeys(ns_keys, email_id)
        msg_keys = MessageKeys(keys, new_uid)
        await _scripts.add(
            redis, ct_keys, keys, msg_keys,
            uid=new_uid, recent=recent,
            flags=[str(flag) for flag in append_msg.flag_set],
            date=when.isoformat().encode('ascii'),
            email_id=email_id, thread_id=thread_id, send_content=send_content,
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
        msg_keys = MessageKeys(keys, uid)
        dest_keys = destination._keys
        pipe = redis.pipeline()
        pipe.incr(dest_keys.max_uid)
        pipe.hget(keys.email_ids, uid)
        dest_uid, email_id = await pipe.execute()
        ct_keys = ContentKeys(self._ns_keys, email_id)
        dest_msg_keys = MessageKeys(dest_keys, dest_uid)
        try:
            await _scripts.copy(redis, ct_keys, keys, dest_keys,
                                msg_keys, dest_msg_keys, recent=recent,
                                source_uid=uid, dest_uid=dest_uid)
        except ReplyError as exc:
            if 'message not found' in str(exc):
                return None
            raise
        return dest_uid

    async def move(self, uid: int, destination: MailboxData, *,
                   recent: bool = False) -> Optional[int]:
        redis = self._redis
        keys = self._keys
        msg_keys = MessageKeys(keys, uid)
        dest_keys = destination._keys
        dest_uid = await redis.incr(dest_keys.max_uid)
        dest_msg_keys = MessageKeys(dest_keys, dest_uid)
        try:
            await _scripts.move(redis, keys, dest_keys, msg_keys,
                                dest_msg_keys, recent=recent,
                                source_uid=uid, dest_uid=dest_uid)
        except ReplyError as exc:
            if 'message not found' in str(exc):
                return None
            raise
        return dest_uid

    async def get(self, uid: int, cached_msg: CachedMessage) -> Message:
        redis = self._redis
        keys = self._keys
        ns_keys = self._ns_keys
        msg_keys = MessageKeys(keys, uid)
        try:
            flags, time, email_id, thread_id = await _scripts.get(
                self._redis, keys, msg_keys, uid=uid)
        except ReplyError as exc:
            if 'message not found' not in str(exc):
                raise
            if not isinstance(cached_msg, Message):
                raise TypeError(cached_msg)
            return Message.copy_expunged(cached_msg)
        msg_flags = {Flag(flag) for flag in flags}
        msg_email_id = ObjectId.maybe(email_id)
        msg_thread_id = ObjectId.maybe(thread_id)
        msg_time = datetime.fromisoformat(time.decode('ascii'))
        return Message(uid, msg_time, msg_flags,
                       email_id=msg_email_id, thread_id=msg_thread_id,
                       redis=redis, ns_keys=ns_keys)

    async def update(self, uid: int, cached_msg: CachedMessage,
                     flag_set: FrozenSet[Flag], mode: FlagOp) -> Message:
        redis = self._redis
        keys = self._keys
        ns_keys = self._ns_keys
        msg_keys = MessageKeys(keys, uid)
        try:
            flags, time, email_id, thread_id = await _scripts.update(
                self._redis, keys, msg_keys,
                uid=uid, flags=[str(flag) for flag in flag_set],
                mode=bytes(mode))
        except ReplyError as exc:
            if 'message not found' not in str(exc):
                raise
            if not isinstance(cached_msg, Message):
                raise TypeError(cached_msg)
            msg = Message.copy_expunged(cached_msg)
            msg.permanent_flags = mode.apply(msg.permanent_flags, flag_set)
            return msg
        msg_flags = {Flag(flag) for flag in flags}
        msg_email_id = ObjectId.maybe(email_id)
        msg_thread_id = ObjectId.maybe(thread_id)
        msg_time = datetime.fromisoformat(time.decode('ascii'))
        return Message(uid, msg_time, msg_flags,
                       email_id=msg_email_id, thread_id=msg_thread_id,
                       redis=redis, ns_keys=ns_keys)

    async def delete(self, uids: Iterable[int]) -> None:
        uids = list(uids)
        if not uids:
            return
        await _scripts.delete(self._redis, self._keys, self._cl_keys,
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

    async def _get_initial(self) \
            -> Tuple[int, Sequence[Message], Sequence[int]]:
        redis = self._redis
        keys = self._keys
        ns_keys = self._ns_keys
        txn = WatchMultiExec(redis, keys.max_mod)
        async for pipe, multi in txn.execute():
            pipe.zrange(keys.seq)
            _, _, uids = await pipe.execute()
            multi.get(keys.max_mod)
            for uid in uids:
                msg_keys = MessageKeys(keys, uid)
                multi.echo(uid)
                multi.smembers(msg_keys.flags)
                multi.hget(keys.dates, uid)
                multi.hget(keys.email_ids, uid)
                multi.hget(keys.thread_ids, uid)
        mod_seq_b, *results = txn.results
        mod_seq = int(mod_seq_b or 0)
        updated: List[Message] = []
        for i in range(0, len(results), 5):
            msg_uid = int(results[i])
            msg_flags = {Flag(flag) for flag in results[i + 1]}
            msg_time = datetime.fromisoformat(results[i + 2].decode('ascii'))
            msg_email_id = ObjectId(results[i + 3])
            msg_thread_id = ObjectId(results[i + 4])
            msg = Message(msg_uid, msg_time, msg_flags,
                          email_id=msg_email_id, thread_id=msg_thread_id,
                          redis=redis, ns_keys=ns_keys)
            updated.append(msg)
        return mod_seq, updated, []

    async def _get_updated(self, last_mod_seq: int) \
            -> Tuple[int, Sequence[Message], Sequence[int]]:
        redis = self._redis
        keys = self._keys
        ns_keys = self._ns_keys
        txn = WatchMultiExec(redis, keys.max_mod)
        async for pipe, multi in txn.execute():
            pipe.zrangebyscore(keys.mod_seq, last_mod_seq)
            _, _, uids = await pipe.execute()
            multi.get(keys.max_mod)
            multi.zrangebyscore(keys.expunged, last_mod_seq)
            for uid in uids:
                msg_keys = MessageKeys(keys, uid)
                multi.echo(uid)
                multi.smembers(msg_keys.flags)
                multi.hget(keys.dates, uid)
                multi.hget(keys.email_ids, uid)
                multi.hget(keys.thread_ids, uid)
        mod_seq_b, expunged_b, *results = txn.results
        mod_seq = int(mod_seq_b or 0)
        expunged = [int(uid_b) for uid_b in expunged_b]
        updated: List[Message] = []
        for i in range(0, len(results), 5):
            msg_uid = int(results[i])
            msg_flags = {Flag(flag) for flag in results[i + 1]}
            msg_time = datetime.fromisoformat(results[i + 2].decode('ascii'))
            msg_email_id = ObjectId(results[i + 3])
            msg_thread_id = ObjectId(results[i + 4])
            msg = Message(msg_uid, msg_time, msg_flags,
                          email_id=msg_email_id, thread_id=msg_thread_id,
                          redis=redis, ns_keys=ns_keys)
            updated.append(msg)
        return mod_seq, updated, expunged


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
        mailboxes = await _set_scripts.list(self._redis, self._keys)
        return ListTree(self.delimiter).update('INBOX', *(
            modutf7_decode(name) for name in mailboxes))

    async def get_mailbox(self, name: str) -> MailboxData:
        redis = self._redis
        name_key = modutf7_encode(name)
        try:
            mbx_id, uid_val = await _set_scripts.get(
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
            await _set_scripts.add(self._redis, self._keys,
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
            await _set_scripts.delete(self._redis, self._keys, self._cl_keys,
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
