
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Optional, Sequence, List, Dict, Tuple, FrozenSet, \
    Iterable, Awaitable

from aioredis import Redis  # type: ignore

from pymap.bytes import HashStream
from pymap.exceptions import MailboxAbort, MailboxNotFound, MailboxConflict
from pymap.flags import FlagOp
from pymap.interfaces.message import CachedMessage
from pymap.listtree import ListTree
from pymap.mailbox import MailboxSnapshot
from pymap.mime import MessageContent
from pymap.parsing.message import PreparedMessage
from pymap.parsing.modutf7 import modutf7_encode, modutf7_decode
from pymap.parsing.specials import ObjectId, FetchRequirement, SequenceSet
from pymap.parsing.specials.flag import Flag, Deleted, Seen
from pymap.selected import SelectedSet, SelectedMailbox
from pymap.threads import ThreadKey

from ._util import WatchMultiExec
from .cleanup import Cleanup
from .keys import NamespaceKeys, ContentKeys, MailboxKeys, MessageKeys
from .message import Message
from ..mailbox import SavedMessage, MailboxDataInterface, MailboxSetInterface

__all__ = ['Message', 'MailboxData', 'MailboxSet']


class MailboxData(MailboxDataInterface[Message]):
    """Implementation of :class:`~pymap.backend.mailbox.MailboxDataInterface`
    for the redis backend.

    """

    def __init__(self, redis: Redis, mailbox_id: bytes, uid_validity: int,
                 keys: MailboxKeys, ns_keys: NamespaceKeys,
                 cleanup: Cleanup) -> None:
        super().__init__()
        self._redis = redis
        self._mailbox_id = ObjectId(mailbox_id)
        self._uid_validity = uid_validity
        self._selected_set = SelectedSet()
        self._keys = keys
        self._ns_keys = ns_keys
        self._cleanup = cleanup

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

    async def save(self, message: bytes) -> SavedMessage:
        redis = self._redis
        ns_keys = self._ns_keys
        content = MessageContent.parse(message)
        new_email_id = ObjectId.random_email_id()
        msg_hash = HashStream(hashlib.sha1()).digest(content)
        thread_keys = ThreadKey.get_all(content.header)
        thread_key_keys = [b'\0'.join(thread_key)
                           for thread_key in thread_keys]
        txn = WatchMultiExec(redis)
        async for pipe, multi in txn.execute():
            await pipe.execute()
            multi.hsetnx(ns_keys.email_ids, msg_hash, new_email_id.value)
            multi.hget(ns_keys.email_ids, msg_hash)
            if thread_key_keys:
                multi.hmget(ns_keys.thread_ids, *thread_key_keys)
            else:
                multi.hmget(ns_keys.thread_ids, b'')
        _, email_id, thread_ids = txn.results
        thread_id_b = next((thread_id for thread_id in thread_ids
                            if thread_id is not None), None)
        if thread_id_b is None:
            thread_id = ObjectId.random_thread_id()
        else:
            thread_id = ObjectId(thread_id_b)
        ct_keys = ContentKeys(ns_keys, email_id)
        txn = WatchMultiExec(redis)
        async for pipe, multi in txn.execute():
            await pipe.execute()
            multi.hset(ct_keys.data, b'full', message)
            multi.hset(ct_keys.data, b'full-json',
                       json.dumps(content.json))
            multi.hset(ct_keys.data, b'header', bytes(content.header))
            multi.hset(ct_keys.data, b'header-json',
                       json.dumps(content.header.json))
            multi.expire(ct_keys.data, self._cleanup.content_expire)
            for thread_key_key in thread_key_keys:
                multi.hsetnx(ns_keys.thread_ids,
                             thread_key_key, thread_id.value)
        return SavedMessage(ObjectId(email_id), thread_id, None)

    async def add(self, message: PreparedMessage, *,
                  recent: bool = False) -> Message:
        redis = self._redis
        keys = self._keys
        ns_keys = self._ns_keys
        when = message.when or datetime.now()
        is_deleted = Deleted in message.flag_set
        is_unseen = Seen not in message.flag_set
        msg_flags = [flag.value for flag in message.flag_set]
        msg_time = when.isoformat().encode('ascii')
        email_id = message.email_id
        thread_id = message.thread_id
        ct_keys = ContentKeys(ns_keys, email_id)
        txn = WatchMultiExec(redis, keys.max_mod, keys.abort)
        async for pipe, multi in txn.execute():
            pipe.mget(keys.max_uid, keys.max_mod, keys.abort)
            _, _, (max_uid, max_mod, abort) = await pipe.execute()
            MailboxAbort.assertFalse(abort)
            new_uid = int(max_uid or 0) + 1
            new_mod = int(max_mod or 0) + 1
            msg_keys = MessageKeys(keys, new_uid)
            multi.set(keys.max_uid, new_uid)
            multi.set(keys.max_mod, new_mod)
            multi.sadd(keys.uids, new_uid)
            multi.zadd(keys.mod_seq, new_mod, new_uid)
            multi.zadd(keys.seq, new_uid, new_uid)
            if recent:
                multi.sadd(keys.recent, new_uid)
            if is_deleted:
                multi.sadd(keys.deleted, new_uid)
            if is_unseen:
                multi.zadd(keys.unseen, new_uid, new_uid)
            if msg_flags:
                multi.sadd(msg_keys.flags, *msg_flags)
            multi.hmset(msg_keys.immutable, b'time', msg_time,
                        b'emailid', email_id.value,
                        b'threadid', thread_id.value)
            multi.persist(ct_keys.data)
            multi.hincrby(ns_keys.content_refs, email_id.value, 1)
        return Message(new_uid, when, message.flag_set,
                       email_id=email_id, thread_id=thread_id,
                       redis=redis, ns_keys=ns_keys)

    async def move(self, uid: int, destination: MailboxData, *,
                   recent: bool = False) -> Optional[int]:
        redis = self._redis
        keys = self._keys
        msg_keys = MessageKeys(keys, uid)
        dest_keys = destination._keys
        txn = WatchMultiExec(redis, keys.max_mod, dest_keys.max_mod,
                             keys.abort, dest_keys.abort, dest_keys.max_uid)
        async for pipe, multi in txn.execute():
            pipe.mget(keys.max_mod, dest_keys.max_mod,
                      keys.abort, dest_keys.abort, dest_keys.max_uid)
            pipe.sismember(keys.uids, uid)
            pipe.smembers(msg_keys.flags)
            _, _, (dest_max_mod, max_mod, abort, dest_abort,
                   dest_max_uid), exists, flags = await pipe.execute()
            if not exists:
                return None
            MailboxAbort.assertFalse(dest_abort)
            MailboxAbort.assertFalse(abort)
            new_mod = int(max_mod or 0) + 1
            msg_flags = {Flag(flag) for flag in flags}
            multi.set(keys.max_mod, new_mod)
            multi.srem(keys.uids, uid)
            multi.zrem(keys.seq, uid)
            multi.zrem(keys.mod_seq, uid)
            multi.srem(keys.recent, uid)
            multi.srem(keys.deleted, uid)
            multi.zrem(keys.unseen, uid)
            multi.zadd(keys.expunged, new_mod, uid)
            dest_uid = int(dest_max_uid or 0) + 1
            dest_new_mod = int(dest_max_mod or 0) + 1
            dest_msg_keys = MessageKeys(dest_keys, dest_uid)
            multi.set(dest_keys.max_uid, dest_uid)
            multi.set(dest_keys.max_mod, dest_new_mod)
            multi.sadd(dest_keys.uids, dest_uid)
            multi.zadd(dest_keys.mod_seq, dest_new_mod, dest_uid)
            multi.zadd(dest_keys.seq, dest_uid, dest_uid)
            if recent:
                multi.sadd(dest_keys.recent, dest_uid)
            if Deleted in msg_flags:
                multi.sadd(dest_keys.deleted, dest_uid)
            if Seen not in msg_flags:
                multi.zadd(dest_keys.unseen, dest_uid, dest_uid)
            if msg_flags:
                multi.rename(msg_keys.flags, dest_msg_keys.flags)
            multi.rename(msg_keys.immutable, dest_msg_keys.immutable)
        return dest_uid

    async def get(self, uid: int, cached_msg: CachedMessage = None,
                  requirement: FetchRequirement = FetchRequirement.METADATA) \
            -> Optional[Message]:
        redis = self._redis
        keys = self._keys
        ns_keys = self._ns_keys
        msg_keys = MessageKeys(keys, uid)
        txn = WatchMultiExec(redis)
        async for pipe, multi in txn.execute():
            await pipe.execute()
            multi.sismember(keys.uids, uid)
            multi.smembers(msg_keys.flags)
            multi.hmget(msg_keys.immutable, b'time', b'emailid', b'threadid')
            multi.get(keys.abort)
        exists, flags, (time, email_id, thread_id), abort = txn.results
        MailboxAbort.assertFalse(abort)
        if not exists:
            if cached_msg is not None:
                if not isinstance(cached_msg, Message):
                    raise TypeError(cached_msg)
                return Message.copy_expunged(cached_msg)
            else:
                return None
        msg_flags = {Flag(flag) for flag in flags}
        msg_email_id = ObjectId.maybe(email_id)
        msg_thread_id = ObjectId.maybe(thread_id)
        msg_time = datetime.fromisoformat(time.decode('ascii'))
        return Message(uid, msg_time, msg_flags,
                       email_id=msg_email_id, thread_id=msg_thread_id,
                       redis=redis, ns_keys=ns_keys)

    async def delete(self, uids: Iterable[int]) -> None:
        redis = self._redis
        keys = self._keys
        uids = list(uids)
        if not uids:
            return
        txn = WatchMultiExec(redis, keys.max_mod, keys.abort)
        async for pipe, multi in txn.execute():
            pipe.mget(keys.max_mod, keys.abort)
            _, _, (max_mod, abort) = await pipe.execute()
            MailboxAbort.assertFalse(abort)
            new_mod = int(max_mod or 0) + 1
            multi.set(keys.max_mod, new_mod)
            multi.srem(keys.uids, *uids)
            multi.zrem(keys.seq, *uids)
            multi.zrem(keys.mod_seq, *uids)
            multi.srem(keys.recent, *uids)
            multi.srem(keys.deleted, *uids)
            multi.zrem(keys.unseen, *uids)
            for uid in uids:
                multi.zadd(keys.expunged, new_mod, uid)
                msg_keys = MessageKeys(keys, uid)
                self._cleanup.add_message(multi, msg_keys)

    async def claim_recent(self, selected: SelectedMailbox) -> None:
        redis = self._redis
        keys = self._keys
        txn = WatchMultiExec(redis, keys.max_mod, keys.abort)
        async for pipe, multi in txn.execute():
            pipe.smembers(keys.recent)
            pipe.mget(keys.max_mod, keys.abort)
            _, _, recent, (max_mod, abort) = await pipe.execute()
            if not recent:
                break
            MailboxAbort.assertFalse(abort)
            new_mod = int(max_mod or 0) + 1
            multi.set(keys.max_mod, new_mod)
            for uid in recent:
                multi.zadd(keys.mod_seq, new_mod, uid)
            multi.delete(keys.recent)
        for uid_bytes in recent:
            selected.session_flags.add_recent(int(uid_bytes))

    async def update_flags(self, messages: Sequence[Message],
                           flag_set: FrozenSet[Flag], mode: FlagOp) -> None:
        redis = self._redis
        keys = self._keys
        messages = list(messages)
        if not messages:
            return
        uids = {msg.uid: msg for msg in messages}
        txn = WatchMultiExec(redis, keys.max_mod, keys.abort)
        async for pipe, multi in txn.execute():
            pipe.smembers(keys.uids)
            pipe.mget(keys.max_mod, keys.abort)
            _, _, existing_uids, (max_mod, abort) = await pipe.execute()
            MailboxAbort.assertFalse(abort)
            update_uids = uids.keys() & {int(uid) for uid in existing_uids}
            new_flags: Dict[int, Awaitable[Sequence[bytes]]] = {}
            if not update_uids:
                break
            new_mod = int(max_mod or 0) + 1
            multi.set(keys.max_mod, new_mod)
            for msg in messages:
                msg_uid = msg.uid
                if msg_uid not in update_uids:
                    continue
                msg_keys = MessageKeys(keys, msg_uid)
                flag_vals = (flag.value for flag in flag_set)
                multi.zadd(keys.mod_seq, new_mod, msg_uid)
                if mode == FlagOp.REPLACE:
                    multi.delete(msg_keys.flags)
                    if flag_set:
                        multi.sadd(msg_keys.flags, *flag_vals)
                    if Deleted in flag_set:
                        multi.sadd(keys.deleted, msg_uid)
                    else:
                        multi.srem(keys.deleted, msg_uid)
                    if Seen not in flag_set:
                        multi.zadd(keys.unseen, msg_uid, msg_uid)
                    else:
                        multi.zrem(keys.unseen, msg_uid)
                elif mode == FlagOp.ADD and flag_set:
                    multi.sadd(msg_keys.flags, *flag_vals)
                    if Deleted in flag_set:
                        multi.sadd(keys.deleted, msg_uid)
                    if Seen in flag_set:
                        multi.zrem(keys.unseen, msg_uid)
                elif mode == FlagOp.DELETE and flag_set:
                    multi.srem(msg_keys.flags, *flag_vals)
                    if Deleted in flag_set:
                        multi.srem(keys.deleted, msg_uid)
                    if Seen in flag_set:
                        multi.zadd(keys.unseen, msg_uid, msg_uid)
                new_flags[msg_uid] = multi.smembers(msg_keys.flags)
        for msg_uid, msg_flags in new_flags.items():
            msg = uids[msg_uid]
            msg.permanent_flags = frozenset(
                Flag(flag) for flag in await msg_flags)

    async def find_deleted(self, seq_set: SequenceSet,
                           selected: SelectedMailbox) -> Sequence[int]:
        if not seq_set.is_all:
            return await super().find_deleted(seq_set, selected)
        redis = self._redis
        pipe = redis.pipeline()
        pipe.unwatch()
        pipe.smembers(self._keys.deleted)
        _, deleted = await pipe.execute()
        return [int(uid) for uid in deleted]

    async def cleanup(self) -> None:
        pass

    async def snapshot(self) -> MailboxSnapshot:
        redis = self._redis
        keys = self._keys
        txn = WatchMultiExec(redis, keys.seq, keys.abort)
        async for pipe, multi in txn.execute():
            pipe.get(keys.abort)
            pipe.zrange(keys.unseen, 0, 0)
            _, _, abort, unseen = await pipe.execute()
            MailboxAbort.assertFalse(abort)
            multi.get(keys.max_uid)
            multi.zcard(keys.seq)
            multi.scard(keys.recent)
            multi.zcard(keys.unseen)
            if unseen:
                multi.zrank(keys.seq, unseen[0])
            else:
                multi.echo(b'')
        max_uid, exists, num_recent, num_unseen, first_unseen_b = txn.results
        next_uid = int(max_uid or 0) + 1
        first_unseen: Optional[int] = None
        if first_unseen_b:
            first_unseen = int(first_unseen_b) + 1
        return MailboxSnapshot(self.mailbox_id, self.readonly,
                               self.uid_validity, self.permanent_flags,
                               self.session_flags, exists, num_recent,
                               num_unseen, first_unseen, next_uid)

    async def _get_initial(self) \
            -> Tuple[int, Sequence[Message], Sequence[int]]:
        redis = self._redis
        keys = self._keys
        ns_keys = self._ns_keys
        txn = WatchMultiExec(redis, keys.max_mod, keys.abort)
        async for pipe, multi in txn.execute():
            pipe.zrange(keys.seq)
            pipe.get(keys.abort)
            _, _, uids, abort = await pipe.execute()
            MailboxAbort.assertFalse(abort)
            multi.get(keys.max_mod)
            for uid in uids:
                msg_keys = MessageKeys(keys, uid)
                multi.echo(uid)
                multi.smembers(msg_keys.flags)
                multi.hmget(msg_keys.immutable,
                            b'time', b'emailid', b'threadid')
        mod_seq_b, *results = txn.results
        mod_seq = int(mod_seq_b or 0)
        updated: List[Message] = []
        for i in range(0, len(results), 3):
            msg_uid = int(results[i])
            msg_flags = {Flag(flag) for flag in results[i + 1]}
            time_b, email_id, thread_id = results[i + 2]
            msg_time = datetime.fromisoformat(time_b.decode('ascii'))
            msg = Message(msg_uid, msg_time, msg_flags,
                          email_id=ObjectId(email_id),
                          thread_id=ObjectId(thread_id),
                          redis=redis, ns_keys=ns_keys)
            updated.append(msg)
        return mod_seq, updated, []

    async def _get_updated(self, last_mod_seq: int) \
            -> Tuple[int, Sequence[Message], Sequence[int]]:
        redis = self._redis
        keys = self._keys
        ns_keys = self._ns_keys
        txn = WatchMultiExec(redis, keys.max_mod, keys.abort)
        async for pipe, multi in txn.execute():
            pipe.zrangebyscore(keys.mod_seq, last_mod_seq)
            pipe.get(keys.abort)
            _, _, uids, abort = await pipe.execute()
            MailboxAbort.assertFalse(abort)
            multi.get(keys.max_mod)
            multi.zrangebyscore(keys.expunged, last_mod_seq)
            for uid in uids:
                msg_keys = MessageKeys(keys, uid)
                multi.echo(uid)
                multi.smembers(msg_keys.flags)
                multi.hmget(msg_keys.immutable,
                            b'time', b'emailid', b'threadid')
        mod_seq_b, expunged_b, *results = txn.results
        mod_seq = int(mod_seq_b or 0)
        expunged = [int(uid_b) for uid_b in expunged_b]
        updated: List[Message] = []
        for i in range(0, len(results), 3):
            msg_uid = int(results[i])
            msg_flags = {Flag(flag) for flag in results[i + 1]}
            time_b, email_id, thread_id = results[i + 2]
            msg_time = datetime.fromisoformat(time_b.decode('ascii'))
            msg = Message(msg_uid, msg_time, msg_flags,
                          email_id=ObjectId(email_id),
                          thread_id=ObjectId(thread_id),
                          redis=redis, ns_keys=ns_keys)
            updated.append(msg)
        return mod_seq, updated, expunged


class MailboxSet(MailboxSetInterface[MailboxData]):
    """Implementation of :class:`~pymap.backend.mailbox.MailboxSetInterface`
    for the redis backend.

    """

    def __init__(self, redis: Redis, keys: NamespaceKeys,
                 cleanup: Cleanup) -> None:
        super().__init__()
        self._redis = redis
        self._keys = keys
        self._cleanup = cleanup

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
        _, mailboxes_raw = await pipe.execute()
        mailboxes = [modutf7_decode(name) for name in mailboxes_raw]
        return ListTree(self.delimiter).update('INBOX', *mailboxes)

    async def list_mailboxes(self) -> ListTree:
        txn = WatchMultiExec(self._redis)
        async for pipe, multi in txn.execute():
            await pipe.execute()
            multi.hgetall(self._keys.mailboxes)
            multi.zrange(self._keys.order)
        mailboxes, mbx_order = txn.results
        rev_mbx = {mbx_id: key for key, mbx_id in mailboxes.items()}
        mailboxes = [modutf7_decode(rev_mbx[mbx_id]) for mbx_id in mbx_order
                     if mbx_id in rev_mbx]
        return ListTree(self.delimiter).update('INBOX', *mailboxes)

    async def get_mailbox(self, name: str,
                          try_create: bool = False) -> MailboxData:
        redis = self._redis
        name_key = modutf7_encode(name)
        txn = WatchMultiExec(redis, self._keys.mailboxes)
        async for pipe, multi in txn.execute():
            pipe.hget(self._keys.mailboxes, name_key)
            _, _, mbx_id = await pipe.execute()
            if mbx_id is None:
                raise MailboxNotFound(name, try_create)
            multi.hget(self._keys.uid_validity, name_key)
        uidval, *_ = txn.results
        mbx_keys = MailboxKeys(self._keys, mbx_id)
        return MailboxData(redis, mbx_id, int(uidval), mbx_keys, self._keys,
                           self._cleanup)

    async def add_mailbox(self, name: str) -> ObjectId:
        name_key = modutf7_encode(name)
        mbx_id = ObjectId.random_mailbox_id()
        txn = WatchMultiExec(self._redis, self._keys.mailboxes)
        async for pipe, multi in txn.execute():
            pipe.incr(self._keys.max_order)
            pipe.hexists(self._keys.mailboxes, name_key)
            _, _, order, exists = await pipe.execute()
            if exists:
                raise MailboxConflict(name)
            multi.hset(self._keys.mailboxes, name_key, mbx_id.value)
            multi.zadd(self._keys.order, order, mbx_id.value)
            multi.hincrby(self._keys.uid_validity, name_key)
        _, _, uidval = txn.results
        return mbx_id

    async def delete_mailbox(self, name: str) -> None:
        name_key = modutf7_encode(name)
        redis = self._redis
        txn = WatchMultiExec(redis)
        async for pipe, multi in txn.execute():
            await pipe.execute()
            multi.hget(self._keys.mailboxes, name_key)
            multi.hdel(self._keys.mailboxes, name_key)
        mbx_id, _ = txn.results
        if mbx_id is None:
            raise MailboxNotFound(name)
        mbx_keys = MailboxKeys(self._keys, mbx_id)
        pipe = redis.pipeline()
        pipe.unwatch()
        pipe.zrem(self._keys.order, mbx_id)
        pipe.set(mbx_keys.abort, 1)
        self._cleanup.add_mailbox(pipe, mbx_keys)
        await pipe.execute()

    async def rename_mailbox(self, before: str, after: str) -> None:
        txn = WatchMultiExec(self._redis, self._keys.mailboxes)
        async for pipe, multi in txn.execute():
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
