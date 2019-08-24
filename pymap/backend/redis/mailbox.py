
import asyncio
import hashlib
from datetime import datetime
from typing import Optional, Sequence, List, Dict, Tuple, FrozenSet, \
    Iterable, Awaitable

from aioredis import Redis, MultiExecError, WatchVariableError  # type: ignore

from pymap.bytes import HashStream
from pymap.exceptions import MailboxAbort, MailboxNotFound, MailboxConflict
from pymap.flags import FlagOp
from pymap.interfaces.message import AppendMessage, CachedMessage
from pymap.listtree import ListTree
from pymap.mailbox import MailboxSnapshot
from pymap.message import BaseMessage, BaseLoadedMessage
from pymap.mime import MessageContent
from pymap.parsing.modutf7 import modutf7_encode, modutf7_decode
from pymap.parsing.specials import ObjectId, FetchRequirement, SequenceSet
from pymap.parsing.specials.flag import Flag, Deleted, Seen
from pymap.selected import SelectedSet, SelectedMailbox
from pymap.threads import ThreadKey

from ..mailbox import MailboxDataInterface, MailboxSetInterface

__all__ = ['Message', 'MailboxData', 'MailboxSet']


async def _delete_keys(redis: Redis, prefixes: Iterable[bytes]) -> None:
    for prefix in prefixes:
        cur = b'0'
        match = prefix + b':*'
        while cur:
            cur, keys = await redis.scan(cur, match=match)
            if keys:
                await redis.unlink(*keys)


async def _check_errors(multi) -> bool:
    # Prevents warning about exception never being retrieved.
    errors = await asyncio.gather(*multi._results, return_exceptions=True)
    return any(not isinstance(exc, WatchVariableError) for exc in errors)


class Message(BaseMessage):

    __slots__ = ['_redis', '_msg_prefix']

    def __init__(self, uid: int, internal_date: datetime,
                 permanent_flags: Iterable[Flag], *, expunged: bool = False,
                 email_id: ObjectId = None, thread_id: ObjectId = None,
                 redis: Redis = None, msg_prefix: bytes = None) -> None:
        super().__init__(uid, internal_date, permanent_flags,
                         expunged=expunged, email_id=email_id,
                         thread_id=thread_id)
        self._redis = redis
        self._msg_prefix = msg_prefix

    async def load_content(self, requirement: FetchRequirement) \
            -> 'RedisMessageContent':
        redis = self._redis
        msg_prefix = self._msg_prefix
        if redis is None or msg_prefix is None or \
                not requirement.overlaps(FetchRequirement.CONTENT):
            return RedisMessageContent(self, None, requirement)
        pipe = redis.pipeline()
        if requirement & FetchRequirement.HEADER:
            pipe.get(msg_prefix + b':header')
        else:
            pipe.echo(b'')
        if requirement & FetchRequirement.BODY:
            pipe.get(msg_prefix + b':body')
        else:
            pipe.echo(b'')
        header, body = await pipe.execute()
        content = MessageContent.parse_split(header, body)
        return RedisMessageContent(self, content, requirement)


class RedisMessageContent(BaseLoadedMessage):
    pass


class MailboxData(MailboxDataInterface[Message]):
    """Implementation of :class:`~pymap.backend.mailbox.MailboxDataInterface`
    for the redis backend.

    """

    def __init__(self, redis: Redis, mailbox_id: bytes, prefix: bytes,
                 email_ids_key: bytes, thread_ids_key: bytes,
                 uid_validity: int) -> None:
        super().__init__()
        self._redis = redis
        self._mailbox_id = ObjectId(mailbox_id)
        self._prefix = prefix
        self._abort_key = prefix + b':abort'
        self._email_ids_key = email_ids_key
        self._thread_ids_key = thread_ids_key
        self._uid_validity = uid_validity
        self._selected_set = SelectedSet()

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

    async def _find_email_id(self, content: MessageContent) -> ObjectId:
        new_email_id = ObjectId.random_email_id()
        msg_hash = HashStream(hashlib.sha1()).digest(content)
        multi = self._redis.multi_exec()
        multi.hsetnx(self._email_ids_key, msg_hash, new_email_id.value)
        multi.hget(self._email_ids_key, msg_hash)
        _, email_id = await multi.execute()
        return ObjectId(email_id)

    async def _find_thread_id(self, content: MessageContent) -> ObjectId:
        redis = self._redis
        thread_keys = ThreadKey.get_all(content.header)
        thread_key_keys = [b'\0'.join(thread_key)
                           for thread_key in thread_keys]
        thread_ids = await redis.hmget(self._thread_ids_key, *thread_key_keys)
        thread_id_b = next((thread_id for thread_id in thread_ids
                            if thread_id is not None), None)
        if thread_id_b is None:
            thread_id = ObjectId.random_thread_id()
        else:
            thread_id = ObjectId(thread_id_b)
        pipe = redis.pipeline()
        for thread_key_key in thread_key_keys:
            redis.hsetnx(self._thread_ids_key, thread_key_key, thread_id.value)
        await pipe.execute()
        return thread_id

    async def add(self, append_msg: AppendMessage, *, recent: bool = False,
                  email_id: ObjectId = None,
                  thread_id: ObjectId = None) -> Message:
        redis = self._redis
        prefix = self._prefix
        msg_content = MessageContent.parse(append_msg.message)
        if email_id is None:
            email_id = await self._find_email_id(msg_content)
        if thread_id is None:
            thread_id = await self._find_thread_id(msg_content)
        is_deleted = Deleted in append_msg.flag_set
        is_unseen = Seen not in append_msg.flag_set
        msg_flags = [flag.value for flag in append_msg.flag_set]
        msg_time = append_msg.when.isoformat().encode('ascii')
        while True:
            await redis.watch(prefix + b':max-mod', self._abort_key)
            max_uid, max_mod, abort = await redis.mget(
                prefix + b':max-uid', prefix + b':max-mod', self._abort_key)
            MailboxAbort.assertFalse(abort)
            new_uid = int(max_uid or 0) + 1
            new_mod = int(max_mod or 0) + 1
            msg_prefix = prefix + b':msg:%d' % new_uid
            multi = redis.multi_exec()
            multi.set(prefix + b':max-uid', new_uid)
            multi.set(prefix + b':max-mod', new_mod)
            multi.sadd(prefix + b':uids', new_uid)
            multi.zadd(prefix + b':mod-sequence', new_mod, new_uid)
            multi.zadd(prefix + b':sequence', new_uid, new_uid)
            if recent:
                multi.sadd(prefix + b':recent', new_uid)
            if is_deleted:
                multi.sadd(prefix + b':deleted', new_uid)
            if is_unseen:
                multi.zadd(prefix + b':unseen', new_uid, new_uid)
            if msg_flags:
                multi.sadd(msg_prefix + b':flags', *msg_flags)
            multi.set(msg_prefix + b':emailid', email_id.value)
            multi.set(msg_prefix + b':threadid', thread_id.value)
            multi.set(msg_prefix + b':time', msg_time)
            multi.set(msg_prefix + b':header', bytes(msg_content.header))
            multi.set(msg_prefix + b':body', bytes(msg_content.body))
            try:
                await multi.execute()
            except MultiExecError:
                if await _check_errors(multi):
                    raise
            else:
                break
        return Message(new_uid, append_msg.when, append_msg.flag_set,
                       email_id=email_id, thread_id=thread_id,
                       redis=redis, msg_prefix=msg_prefix)

    async def get(self, uid: int, cached_msg: CachedMessage = None,
                  requirement: FetchRequirement = FetchRequirement.METADATA) \
            -> Optional[Message]:
        redis = self._redis
        prefix = self._prefix
        msg_prefix = prefix + b':msg:%d' % uid
        multi = redis.multi_exec()
        multi.sismember(prefix + b':uids', uid)
        multi.smembers(msg_prefix + b':flags')
        multi.get(msg_prefix + b':emailid')
        multi.get(msg_prefix + b':threadid')
        multi.get(msg_prefix + b':time')
        multi.get(self._abort_key)
        exists, flags, email_id, thread_id, time, abort = await multi.execute()
        MailboxAbort.assertFalse(abort)
        if not exists:
            if cached_msg is None:
                return None
            else:
                return Message(cached_msg.uid, cached_msg.internal_date,
                               cached_msg.permanent_flags, expunged=True)
        msg_flags = {Flag(flag) for flag in flags}
        msg_email_id = ObjectId.maybe(email_id)
        msg_thread_id = ObjectId.maybe(thread_id)
        msg_time = datetime.fromisoformat(time.decode('ascii'))
        return Message(uid, msg_time, msg_flags,
                       email_id=msg_email_id, thread_id=msg_thread_id,
                       redis=redis, msg_prefix=msg_prefix)

    async def delete(self, uids: Iterable[int]) -> None:
        redis = self._redis
        prefix = self._prefix
        uids = list(uids)
        if not uids:
            return
        while True:
            await redis.watch(prefix + b':max-mod', self._abort_key)
            max_mod, abort = await redis.mget(prefix + b':max-mod',
                                              self._abort_key)
            MailboxAbort.assertFalse(abort)
            new_mod = int(max_mod or 0) + 1
            multi = redis.multi_exec()
            multi.set(prefix + b':max-mod', new_mod)
            for uid in uids:
                multi.zadd(prefix + b':expunged', new_mod, uid)
            multi.srem(prefix + b':uids', *uids)
            multi.zrem(prefix + b':sequence', *uids)
            multi.zrem(prefix + b':mod-sequence', *uids)
            multi.srem(prefix + b':recent', *uids)
            multi.srem(prefix + b':deleted', *uids)
            multi.zrem(prefix + b':unseen', *uids)
            multi.sadd(prefix + b':cleanup', *uids)
            try:
                await multi.execute()
            except MultiExecError:
                if await _check_errors(multi):
                    raise
            else:
                break

    async def claim_recent(self, selected: SelectedMailbox) -> None:
        redis = self._redis
        prefix = self._prefix
        while True:
            await redis.watch(prefix + b':max-mod', self._abort_key)
            recent = await redis.smembers(prefix + b':recent')
            if not recent:
                break
            max_mod, abort = await redis.mget(prefix + b':max-mod',
                                              self._abort_key)
            MailboxAbort.assertFalse(abort)
            new_mod = int(max_mod or 0) + 1
            multi = self._redis.multi_exec()
            multi.set(prefix + b':max-mod', new_mod)
            for uid in recent:
                multi.zadd(prefix + b':mod-sequence', new_mod, uid)
            multi.delete(prefix + b':recent')
            try:
                await multi.execute()
            except MultiExecError:
                if await _check_errors(multi):
                    raise
            else:
                break
        for uid_bytes in recent:
            selected.session_flags.add_recent(int(uid_bytes))

    async def update_flags(self, messages: Sequence[Message],
                           flag_set: FrozenSet[Flag], mode: FlagOp) -> None:
        redis = self._redis
        prefix = self._prefix
        messages = list(messages)
        if not messages:
            return
        uids = {msg.uid: msg for msg in messages}
        while True:
            await redis.watch(prefix + b':max-mod', self._abort_key)
            pipe = redis.pipeline()
            pipe.smembers(prefix + b':uids')
            pipe.get(prefix + b':max-mod')
            pipe.get(self._abort_key)
            existing_uids, max_mod, abort = await pipe.execute()
            MailboxAbort.assertFalse(abort)
            update_uids = uids.keys() & {int(uid) for uid in existing_uids}
            if not update_uids:
                break
            new_mod = int(max_mod or 0) + 1
            new_flags: Dict[int, Awaitable[Sequence[bytes]]] = {}
            multi = redis.multi_exec()
            multi.set(prefix + b':max-mod', new_mod)
            for msg in messages:
                msg_uid = msg.uid
                if msg_uid not in update_uids:
                    continue
                msg_prefix = prefix + b':msg:%d' % msg_uid
                flag_vals = (flag.value for flag in flag_set)
                multi.zadd(prefix + b':mod-sequence', new_mod, msg_uid)
                if mode == FlagOp.REPLACE:
                    multi.unlink(msg_prefix + b':flags')
                    if flag_set:
                        multi.sadd(msg_prefix + b':flags', *flag_vals)
                    if Deleted in flag_set:
                        multi.sadd(prefix + b':deleted', msg_uid)
                    else:
                        multi.srem(prefix + b':deleted', msg_uid)
                    if Seen not in flag_set:
                        multi.zadd(prefix + b':unseen', msg_uid, msg_uid)
                    else:
                        multi.zrem(prefix + b':unseen', msg_uid)
                elif mode == FlagOp.ADD and flag_set:
                    multi.sadd(msg_prefix + b':flags', *flag_vals)
                    if Deleted in flag_set:
                        multi.sadd(prefix + b':deleted', msg_uid)
                    if Seen in flag_set:
                        multi.zrem(prefix + b':unseen', msg_uid)
                elif mode == FlagOp.DELETE and flag_set:
                    multi.srem(msg_prefix + b':flags', *flag_vals)
                    if Deleted in flag_set:
                        multi.srem(prefix + b':deleted', msg_uid)
                    if Seen in flag_set:
                        multi.zadd(prefix + b':unseen', msg_uid, msg_uid)
                new_flags[msg_uid] = multi.smembers(msg_prefix + b':flags')
            try:
                await multi.execute()
            except MultiExecError:
                if await _check_errors(multi):
                    raise
            else:
                for msg_uid, msg_flags in new_flags.items():
                    msg = uids[msg_uid]
                    msg.permanent_flags = frozenset(
                        Flag(flag) for flag in await msg_flags)
                break

    async def cleanup(self) -> None:
        redis = self._redis
        prefix = self._prefix
        while True:
            uids = await redis.spop(prefix + b':cleanup', 100)
            if not uids:
                break
            prefixes = (prefix + b':msg:%b' % uid for uid in uids)
            await _delete_keys(redis, prefixes)

    async def find_deleted(self, seq_set: SequenceSet,
                           selected: SelectedMailbox) -> Sequence[int]:
        if not seq_set.is_all:
            return await super().find_deleted(seq_set, selected)
        redis = self._redis
        prefix = self._prefix
        deleted = await redis.smembers(prefix + b':deleted')
        return [int(uid) for uid in deleted]

    async def snapshot(self) -> MailboxSnapshot:
        redis = self._redis
        prefix = self._prefix
        while True:
            await redis.watch(prefix + b':sequence', self._abort_key)
            pipe = redis.pipeline()
            pipe.get(prefix + b':max-uid')
            pipe.zcard(prefix + b':sequence')
            pipe.scard(prefix + b':recent')
            pipe.zcard(prefix + b':unseen')
            pipe.zrange(prefix + b':unseen', 0, 0)
            pipe.get(self._abort_key)
            max_uid, exists, num_recent, num_unseen, unseen, abort = \
                await pipe.execute()
            MailboxAbort.assertFalse(abort)
            next_uid = int(max_uid or 0) + 1
            if not unseen:
                first_unseen: Optional[int] = None
                break
            else:
                first_uid = int(unseen[0])
                multi = redis.multi_exec()
                multi.zrank(prefix + b':sequence', first_uid)
                try:
                    [first_unseen] = await multi.execute()
                except MultiExecError:
                    if await _check_errors(multi):
                        raise
                else:
                    break
        return MailboxSnapshot(self.mailbox_id, self.readonly,
                               self.uid_validity, self.permanent_flags,
                               self.session_flags, exists, num_recent,
                               num_unseen, first_unseen, next_uid)

    async def _get_initial(self) \
            -> Tuple[int, Sequence[Message], Sequence[int]]:
        redis = self._redis
        prefix = self._prefix
        while True:
            await redis.watch(prefix + b':max-mod', self._abort_key)
            pipe = redis.pipeline()
            pipe.zrange(prefix + b':sequence')
            pipe.get(self._abort_key)
            uids, abort = await pipe.execute()
            MailboxAbort.assertFalse(abort)
            multi = redis.multi_exec()
            multi.get(prefix + b':max-mod')
            for uid in uids:
                msg_prefix = prefix + b':msg:' + uid
                multi.echo(uid)
                multi.smembers(msg_prefix + b':flags')
                multi.get(msg_prefix + b':time')
            try:
                results = await multi.execute()
            except MultiExecError:
                if await _check_errors(multi):
                    raise
            else:
                break
        mod_seq = int(results[0] or 0)
        updated: List[Message] = []
        for i in range(1, len(results), 3):
            msg_uid = int(results[i])
            msg_flags = {Flag(flag) for flag in results[i + 1]}
            msg_time = datetime.fromisoformat(results[i + 2].decode('ascii'))
            msg = Message(msg_uid, msg_time, msg_flags)
            updated.append(msg)
        return mod_seq, updated, []

    async def _get_updated(self, last_mod_seq: int) \
            -> Tuple[int, Sequence[Message], Sequence[int]]:
        redis = self._redis
        prefix = self._prefix
        while True:
            await redis.watch(prefix + b':max-mod', self._abort_key)
            pipe = redis.pipeline()
            pipe.zrangebyscore(prefix + b':mod-sequence', last_mod_seq)
            pipe.get(self._abort_key)
            uids, abort = await pipe.execute()
            MailboxAbort.assertFalse(abort)
            multi = redis.multi_exec()
            multi.get(prefix + b':max-mod')
            multi.zrangebyscore(prefix + b':expunged', last_mod_seq)
            for uid in uids:
                msg_prefix = prefix + b':msg:' + uid
                multi.echo(uid)
                multi.smembers(msg_prefix + b':flags')
                multi.get(msg_prefix + b':time')
            try:
                results = await multi.execute()
            except MultiExecError:
                if await _check_errors(multi):
                    raise
            else:
                break
        mod_seq = int(results[0] or 0)
        expunged = [int(uid) for uid in results[1]]
        updated: List[Message] = []
        for i in range(2, len(results), 3):
            msg_uid = int(results[i])
            msg_flags = {Flag(flag) for flag in results[i + 1]}
            msg_time = datetime.fromisoformat(results[i + 2].decode('ascii'))
            msg = Message(msg_uid, msg_time, msg_flags)
            updated.append(msg)
        return mod_seq, updated, expunged


class MailboxSet(MailboxSetInterface[MailboxData]):
    """Implementation of :class:`~pymap.backend.mailbox.MailboxSetInterface`
    for the redis backend.

    """

    def __init__(self, redis: Redis, prefix: bytes) -> None:
        super().__init__()
        self._redis = redis
        self._prefix = prefix
        self._mbx_key = prefix + b':mailboxes'
        self._max_order_key = prefix + b':mbx-max-order'
        self._order_key = prefix + b':mbx-order'
        self._uidv_key = prefix + b':uid-validity'
        self._sub_key = prefix + b':subscribed'
        self._email_ids_key = prefix + b':emailids'
        self._thread_ids_key = prefix + b':threadids'

    @property
    def delimiter(self) -> str:
        return '/'

    async def set_subscribed(self, name: str, subscribed: bool) -> None:
        if subscribed:
            await self._redis.sadd(self._sub_key, name)
        else:
            await self._redis.srem(self._sub_key, name)

    async def list_subscribed(self) -> ListTree:
        mailboxes = [modutf7_decode(name) for name in
                     await self._redis.smembers(self._sub_key)]
        return ListTree(self.delimiter).update('INBOX', *mailboxes)

    async def list_mailboxes(self) -> ListTree:
        multi = self._redis.multi_exec()
        multi.hgetall(self._mbx_key)
        multi.zrange(self._order_key)
        mailboxes, mbx_order = await multi.execute()
        rev_mbx = {mbx_id: key for key, mbx_id in mailboxes.items()}
        mailboxes = [modutf7_decode(rev_mbx[mbx_id]) for mbx_id in mbx_order
                     if mbx_id in rev_mbx]
        return ListTree(self.delimiter).update('INBOX', *mailboxes)

    async def get_mailbox(self, name: str,
                          try_create: bool = False) -> 'MailboxData':
        redis = self._redis
        name_key = modutf7_encode(name)
        while True:
            await redis.watch(self._mbx_key)
            mbx_id = await redis.hget(self._mbx_key, name_key)
            if mbx_id is None:
                raise MailboxNotFound(name, try_create)
            multi = redis.multi_exec()
            multi.hget(self._uidv_key, name_key)
            try:
                uidval, *_ = await multi.execute()
            except MultiExecError:
                if await _check_errors(multi):
                    raise
            else:
                mbx_prefix = b'%b:%b' % (self._prefix, mbx_id)
                return MailboxData(redis, mbx_id, mbx_prefix,
                                   self._email_ids_key, self._thread_ids_key,
                                   int(uidval))

    async def add_mailbox(self, name: str) -> ObjectId:
        redis = self._redis
        name_key = modutf7_encode(name)
        while True:
            await redis.watch(self._mbx_key)
            mbx_id = ObjectId.random_mailbox_id()
            pipe = redis.pipeline()
            pipe.incr(self._max_order_key)
            pipe.hexists(self._mbx_key, name_key)
            order, exists = await pipe.execute()
            if exists:
                raise MailboxConflict(name)
            multi = redis.multi_exec()
            multi.hset(self._mbx_key, name_key, mbx_id.value)
            multi.zadd(self._order_key, order, mbx_id.value)
            multi.hincrby(self._uidv_key, name_key)
            try:
                _, _, uidval = await multi.execute()
            except MultiExecError:
                if await _check_errors(multi):
                    raise
            else:
                break
        return mbx_id

    async def delete_mailbox(self, name: str) -> None:
        redis = self._redis
        name_key = modutf7_encode(name)
        multi = redis.multi_exec()
        multi.hget(self._mbx_key, name_key)
        multi.hdel(self._mbx_key, name_key)
        mbx_id, _ = await multi.execute()
        if mbx_id is None:
            raise MailboxNotFound(name)
        await redis.zrem(self._order_key, mbx_id)
        mbx_prefix = b'%b:%b' % (self._prefix, mbx_id)
        await redis.set(mbx_prefix + b':abort', 1)
        asyncio.create_task(_delete_keys(redis, [mbx_prefix]))

    async def rename_mailbox(self, before: str, after: str) -> None:
        redis = self._redis
        while True:
            await redis.watch(self._mbx_key)
            all_keys = await redis.hgetall(self._mbx_key)
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
                multi.hset(self._mbx_key, after_key, before_id)
                multi.hdel(self._mbx_key, before_key)
                multi.hincrby(self._uidv_key, after_key)
            if before == 'INBOX':
                inbox_id = ObjectId.random_mailbox_id()
                multi.hset(self._mbx_key, b'INBOX', inbox_id.value)
                multi.hincrby(self._uidv_key, b'INBOX')
            try:
                await multi.execute()
            except MultiExecError:
                if await _check_errors(multi):
                    raise
            else:
                break
