
import asyncio
from datetime import datetime
from typing import Optional, Sequence, List, Dict, Tuple, FrozenSet, \
    Iterable, Awaitable

from aioredis import Redis, MultiExecError, WatchVariableError  # type: ignore

from pymap.exceptions import MailboxNotFound, MailboxConflict
from pymap.flags import FlagOp
from pymap.interfaces.message import AppendMessage, CachedMessage
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

    def __init__(self, redis: Redis, name: str, prefix: bytes,
                 uid_validity: int) -> None:
        super().__init__()
        self._redis = redis
        self._prefix = prefix
        self._uid_validity = uid_validity
        self._name = name
        self._selected_set = SelectedSet()

    @property
    def name(self) -> str:
        return self._name

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
        selected.uid_validity = self.uid_validity
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
            await redis.watch(prefix + b':max-mod')
            max_uid, max_mod = await redis.mget(prefix + b':max-uid',
                                                prefix + b':max-mod')
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
        exists, flags, time, recent, header, body = await multi.execute()
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
            await redis.watch(prefix + b':max-mod')
            max_mod = await redis.get(prefix + b':max-mod')
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
            try:
                await multi.execute()
            except MultiExecError:
                if await _check_errors(multi):
                    raise
            else:
                break
        prefixes = (prefix + b':msg:%d' % uid for uid in uids)
        asyncio.create_task(_delete_keys(redis, prefixes))

    async def claim_recent(self, selected: SelectedMailbox) -> None:
        redis = self._redis
        prefix = self._prefix
        while True:
            await redis.watch(prefix + b':max-mod')
            recent = await redis.smembers(prefix + b':recent')
            if not recent:
                await redis.unwatch()
                break
            max_mod = await redis.get(prefix + b':max-mod')
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
            await redis.watch(prefix + b':max-mod')
            pipe = redis.pipeline()
            pipe.smembers(prefix + b':uids')
            pipe.get(prefix + b':max-mod')
            existing_uids, max_mod = await pipe.execute()
            update_uids = uids.keys() & {int(uid) for uid in existing_uids}
            if not update_uids:
                await redis.unwatch()
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
                elif mode == FlagOp.ADD and flag_set:
                    multi.sadd(msg_prefix + b':flags', *flag_vals)
                elif mode == FlagOp.DELETE and flag_set:
                    multi.srem(msg_prefix + b':flags', *flag_vals)
                new_flags[msg_uid] = multi.smembers(msg_prefix + b':flags')
                if Deleted in msg.permanent_flags:
                    multi.sadd(prefix + b':deleted', msg_uid)
                else:
                    multi.srem(prefix + b':deleted', msg_uid)
                if Seen not in msg.permanent_flags:
                    multi.zadd(prefix + b':unseen', msg_uid, msg_uid)
                else:
                    multi.zrem(prefix + b':unseen', msg_uid)
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
        pass

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
            await redis.watch(prefix + b':sequence')
            pipe = redis.pipeline()
            pipe.get(prefix + b':max-uid')
            pipe.zcard(prefix + b':sequence')
            pipe.scard(prefix + b':recent')
            pipe.zcard(prefix + b':unseen')
            pipe.zrange(prefix + b':unseen', 0, 0)
            max_uid, exists, num_recent, num_unseen, unseen = \
                await pipe.execute()
            next_uid = int(max_uid or 0) + 1
            if not unseen:
                await redis.unwatch()
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
        return MailboxSnapshot(self.name, self.readonly, self.uid_validity,
                               self.permanent_flags, self.session_flags,
                               exists, num_recent, num_unseen, first_unseen,
                               next_uid)

    async def _get_initial(self) \
            -> Tuple[int, Sequence[Message], Sequence[int]]:
        redis = self._redis
        prefix = self._prefix
        while True:
            await redis.watch(prefix + b':max-mod')
            uids = await redis.zrange(prefix + b':sequence')
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
            await redis.watch(prefix + b':max-mod')
            uids = await redis.zrangebyscore(
                prefix + b':mod-sequence', last_mod_seq)
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
        self._order_key = prefix + b':mbx-order'
        self._mbx_key = prefix + b':mailboxes'
        self._sub_key = prefix + b':subscribed'
        self._uidv_key = prefix + b':uid-validity'

    @property
    def delimiter(self) -> str:
        return '/'

    async def set_subscribed(self, name: str, subscribed: bool) -> None:
        if subscribed:
            await self._redis.sadd(self._sub_key, name)
        else:
            await self._redis.srem(self._sub_key, name)

    async def list_subscribed(self) -> Sequence[str]:
        return [modutf7_decode(name) for name in
                await self._redis.smembers(self._sub_key)]

    async def list_mailboxes(self) -> Sequence[str]:
        return [modutf7_decode(name) for name in
                await self._redis.zrange(self._mbx_key)]

    async def get_mailbox(self, name: str,
                          try_create: bool = False) -> 'MailboxData':
        redis = self._redis
        name_key = modutf7_encode(name)
        multi = redis.multi_exec()
        multi.zscore(self._mbx_key, name_key)
        multi.hget(self._uidv_key, name_key)
        exists, uidval = await multi.execute()
        if not exists:
            raise MailboxNotFound(name, try_create)
        mbx_prefix = b':'.join((self._prefix, name_key, uidval))
        return MailboxData(redis, name, mbx_prefix, int(uidval))

    async def add_mailbox(self, name: str) -> 'MailboxData':
        redis = self._redis
        name_key = modutf7_encode(name)
        while True:
            await redis.watch(self._mbx_key)
            exists = await redis.zscore(self._mbx_key, name_key)
            if exists:
                await redis.unwatch()
                raise MailboxConflict(name)
            order = await redis.incr(self._order_key)
            multi = redis.multi_exec()
            multi.hincrby(self._uidv_key, name_key)
            multi.zadd(self._mbx_key, order, name_key)
            try:
                uidval, _ = await multi.execute()
            except MultiExecError:
                if await _check_errors(multi):
                    raise
            else:
                mbx_prefix = b':'.join(
                    (self._prefix, name_key, b'%d' % uidval))
                return MailboxData(redis, name, mbx_prefix, uidval)

    async def delete_mailbox(self, name: str) -> None:
        redis = self._redis
        name_key = modutf7_encode(name)
        multi = redis.multi_exec()
        multi.hget(self._uidv_key, name_key)
        multi.zrem(self._mbx_key, name_key)
        uidval, exists = await multi.execute()
        if not exists:
            raise MailboxNotFound(name)
        mbx_prefix = b':'.join((self._prefix, name_key, uidval))
        asyncio.create_task(_delete_keys(redis, [mbx_prefix]))

    async def rename_mailbox(self, before: str, after: str) -> 'MailboxData':
        raise NotImplementedError()  # TODO
