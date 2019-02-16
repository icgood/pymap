
import asyncio
import random
from datetime import datetime
from typing import Optional, Sequence, List, Dict, Tuple, FrozenSet, \
    Iterable, Awaitable

from aioredis import Redis, MultiExecError, WatchVariableError  # type: ignore

from pymap.exceptions import MailboxAbort, MailboxNotFound, MailboxConflict
from pymap.flags import FlagOp
from pymap.interfaces.message import AppendMessage, CachedMessage
from pymap.listtree import ListTree
from pymap.mailbox import MailboxSnapshot
from pymap.mime import MessageContent
from pymap.parsing.modutf7 import modutf7_encode, modutf7_decode
from pymap.parsing.specials import FetchRequirement, SequenceSet
from pymap.parsing.specials.flag import Flag, Deleted, Seen
from pymap.selected import SelectedSet, SelectedMailbox

from ..mailbox import Message, MailboxDataInterface, MailboxSetInterface

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


class MailboxData(MailboxDataInterface[Message]):
    """Implementation of :class:`~pymap.backend.mailbox.MailboxDataInterface`
    for the redis backend.

    """

    def __init__(self, redis: Redis, guid: bytes, prefix: bytes,
                 uid_validity: int) -> None:
        super().__init__()
        self._redis = redis
        self._guid = guid
        self._prefix = prefix
        self._abort_key = prefix + b':abort'
        self._uid_validity = uid_validity
        self._selected_set = SelectedSet()

    @property
    def guid(self) -> bytes:
        return self._guid

    @property
    def readonly(self) -> bool:
        return False

    @property
    def uid_validity(self) -> int:
        return self._uid_validity

    @property
    def selected_set(self) -> SelectedSet:
        return self._selected_set

    def parse_message(self, append_msg: AppendMessage) -> Message:
        return Message.parse(0, append_msg.message, append_msg.flag_set,
                             append_msg.when, recent=True)

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

    async def add(self, append_msg: AppendMessage, recent: bool = False) \
            -> Message:
        redis = self._redis
        prefix = self._prefix
        is_deleted = Deleted in append_msg.flag_set
        is_unseen = Seen not in append_msg.flag_set
        msg_content = MessageContent.parse(append_msg.message)
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
        return Message(new_uid, append_msg.flag_set, append_msg.when,
                       recent=recent, content=msg_content)

    async def get(self, uid: int, cached_msg: CachedMessage = None,
                  requirement: FetchRequirement = FetchRequirement.METADATA) \
            -> Optional[Message]:
        redis = self._redis
        prefix = self._prefix
        msg_prefix = prefix + b':msg:%d' % uid
        multi = redis.multi_exec()
        multi.sismember(prefix + b':uids', uid)
        multi.smembers(msg_prefix + b':flags')
        multi.get(msg_prefix + b':time')
        multi.sismember(prefix + b':recent', uid)
        if requirement & FetchRequirement.BODY:
            multi.get(msg_prefix + b':header')
            multi.get(msg_prefix + b':body')
        elif requirement & FetchRequirement.HEADERS:
            multi.get(msg_prefix + b':header')
            multi.echo(b'')
        else:
            multi.echo(b'')
            multi.echo(b'')
        multi.get(self._abort_key)
        exists, flags, time, recent, header, body, abort = \
            await multi.execute()
        MailboxAbort.assertFalse(abort)
        if not exists:
            if cached_msg is None:
                return None
            else:
                return Message(cached_msg.uid, cached_msg.permanent_flags,
                               cached_msg.internal_date, expunged=True)
        msg_flags = {Flag(flag) for flag in flags}
        msg_time = datetime.fromisoformat(time.decode('ascii'))
        msg_recent = bool(recent)
        if header:
            msg_content = MessageContent.parse_split(header, body)
            return Message(uid, msg_flags, msg_time, recent=msg_recent,
                           content=msg_content)
        else:
            return Message(uid, msg_flags, msg_time, recent=msg_recent)

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
            # TODO: use spop with count= when aioredis > 1.2.0 is tagged
            uids = await redis.srandmember(prefix + b':cleanup', 100)
            if not uids:
                break
            prefixes = (prefix + b':msg:%b' % uid for uid in uids)
            await _delete_keys(redis, prefixes)
            await redis.srem(prefix + b':cleanup', *uids)

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
        return MailboxSnapshot(self.guid, self.readonly, self.uid_validity,
                               self.permanent_flags, self.session_flags,
                               exists, num_recent, num_unseen, first_unseen,
                               next_uid)

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
            msg = Message(msg_uid, msg_flags, msg_time)
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
            msg = Message(msg_uid, msg_flags, msg_time)
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
        rev_mbx = {guid: key for key, guid in mailboxes.items()}
        mailboxes = [modutf7_decode(rev_mbx[guid]) for guid in mbx_order
                     if guid in rev_mbx]
        return ListTree(self.delimiter).update('INBOX', *mailboxes)

    async def get_mailbox(self, name: str,
                          try_create: bool = False) -> 'MailboxData':
        redis = self._redis
        name_key = modutf7_encode(name)
        while True:
            await redis.watch(self._mbx_key)
            mbx_guid = await redis.hget(self._mbx_key, name_key)
            if mbx_guid is None:
                raise MailboxNotFound(name, try_create)
            multi = redis.multi_exec()
            multi.hget(self._uidv_key, name_key)
            try:
                uidval, *_ = await multi.execute()
            except MultiExecError:
                if await _check_errors(multi):
                    raise
            else:
                mbx_prefix = b'%b:%b' % (self._prefix, mbx_guid)
                return MailboxData(redis, mbx_guid, mbx_prefix, int(uidval))

    async def add_mailbox(self, name: str) -> None:
        redis = self._redis
        name_key = modutf7_encode(name)
        while True:
            await redis.watch(self._mbx_key)
            mbx_guid = b'%032x' % random.getrandbits(128)
            pipe = redis.pipeline()
            pipe.incr(self._max_order_key)
            pipe.hexists(self._mbx_key, name_key)
            order, exists = await pipe.execute()
            if exists:
                raise MailboxConflict(name)
            multi = redis.multi_exec()
            multi.hset(self._mbx_key, name_key, mbx_guid)
            multi.zadd(self._order_key, order, mbx_guid)
            multi.hincrby(self._uidv_key, name_key)
            try:
                _, _, uidval = await multi.execute()
            except MultiExecError:
                if await _check_errors(multi):
                    raise
            else:
                break

    async def delete_mailbox(self, name: str) -> None:
        redis = self._redis
        name_key = modutf7_encode(name)
        multi = redis.multi_exec()
        multi.hget(self._mbx_key, name_key)
        multi.hdel(self._mbx_key, name_key)
        mbx_guid, _ = await multi.execute()
        if mbx_guid is None:
            raise MailboxNotFound(name)
        await redis.zrem(self._order_key, mbx_guid)
        mbx_prefix = b'%b:%b' % (self._prefix, mbx_guid)
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
                before_guid = all_mbx[before_name]
                before_key = modutf7_encode(before_name)
                after_key = modutf7_encode(after_name)
                multi.hset(self._mbx_key, after_key, before_guid)
                multi.hdel(self._mbx_key, before_key)
                multi.hincrby(self._uidv_key, after_key)
            if before == 'INBOX':
                inbox_guid = b'%032x' % random.getrandbits(128)
                multi.hset(self._mbx_key, b'INBOX', inbox_guid)
                multi.hincrby(self._uidv_key, b'INBOX')
            try:
                await multi.execute()
            except MultiExecError:
                if await _check_errors(multi):
                    raise
            else:
                break
