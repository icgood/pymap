
from __future__ import annotations

from typing import Any, Tuple, Sequence, Mapping, Optional
from typing_extensions import Final

from aioredis import Redis  # type: ignore

from . import ScriptBase
from ..keys import CleanupKeys, NamespaceKeys, ContentKeys, MailboxKeys

__all__ = ['MailboxScripts', 'MailboxSetScripts']


class MailboxScripts:

    def __init__(self) -> None:
        super().__init__()
        self.prepare: Final = MessagePrepare()
        self.add: Final = MessageAdd()
        self.copy: Final = MessageCopy()
        self.move: Final = MessageMove()
        self.update: Final = MessageUpdate()
        self.delete: Final = MessageDelete()
        self.snapshot: Final = MailboxSnapshot()


class MailboxSetScripts:

    def __init__(self) -> None:
        super().__init__()
        self.list: Final = MailboxList()
        self.get: Final = MailboxGet()
        self.add: Final = MailboxAdd()
        self.delete: Final = MailboxDelete()


class MessagePrepare(ScriptBase[Tuple[int, bytes, bytes, bool]]):

    def __init__(self) -> None:
        super().__init__('message_prepare')

    def _convert(self, ret: Tuple[bytes, bytes, bytes, bytes]) \
            -> Tuple[int, bytes, bytes, bool]:
        return (int(ret[0]), ret[1], ret[2], bool(int(ret[3] or 0)))

    async def __call__(self, redis: Redis,
                       ns_keys: NamespaceKeys, mbx_keys: MailboxKeys, *,
                       new_email_id: bytes, new_thread_id: bytes,
                       content_hash: bytes, thread_keys: Sequence[str]) \
            -> Tuple[int, bytes, bytes, bool]:
        keys = [mbx_keys.max_uid, ns_keys.email_ids, ns_keys.thread_ids]
        return await self.eval(redis, keys, [
            new_email_id, new_thread_id, content_hash,
            self._json(thread_keys)])


class MessageAdd(ScriptBase[None]):

    def __init__(self) -> None:
        super().__init__('message_add')

    async def __call__(self, redis: Redis, ns_keys: NamespaceKeys,
                       ct_keys: ContentKeys, mbx_keys: MailboxKeys, *,
                       uid: int, recent: bool, date: bytes,
                       flags: Sequence[str], email_id: bytes,
                       thread_id: bytes, send_content: bool,
                       message: bytes, message_json: Mapping[str, Any],
                       header: bytes, header_json: Mapping[str, Any]) -> None:
        keys = [mbx_keys.uids, mbx_keys.seq, mbx_keys.content,
                mbx_keys.changes, mbx_keys.recent, mbx_keys.deleted,
                mbx_keys.unseen, ns_keys.content_refs, ct_keys.data]
        if send_content:
            content_args = [message, self._json(message_json),
                            header, self._json(header_json)]
        else:
            content_args = []
        return await self.eval(redis, keys, [
            uid, int(recent), self._json(flags), date, email_id, thread_id,
            *content_args])


class MessageCopy(ScriptBase[None]):

    def __init__(self) -> None:
        super().__init__('message_copy')

    async def __call__(self, redis: Redis, ns_keys: NamespaceKeys,
                       mbx_keys: MailboxKeys, dest_mbx_keys: MailboxKeys,
                       source_uid: int, recent: bool) -> None:
        keys = [mbx_keys.uids, dest_mbx_keys.max_uid, dest_mbx_keys.uids,
                dest_mbx_keys.seq, dest_mbx_keys.content,
                dest_mbx_keys.changes, dest_mbx_keys.recent,
                dest_mbx_keys.deleted, dest_mbx_keys.unseen,
                ns_keys.content_refs]
        return await self.eval(redis, keys, [
            source_uid, int(recent)])


class MessageMove(ScriptBase[None]):

    def __init__(self) -> None:
        super().__init__('message_move')

    async def __call__(self, redis: Redis,
                       mbx_keys: MailboxKeys, dest_mbx_keys: MailboxKeys,
                       source_uid: int, recent: bool) -> None:
        keys = [mbx_keys.uids, mbx_keys.seq, mbx_keys.content,
                mbx_keys.changes, mbx_keys.recent, mbx_keys.deleted,
                mbx_keys.unseen, dest_mbx_keys.max_uid, dest_mbx_keys.uids,
                dest_mbx_keys.seq, dest_mbx_keys.content,
                dest_mbx_keys.changes, dest_mbx_keys.recent,
                dest_mbx_keys.deleted, dest_mbx_keys.unseen]
        return await self.eval(redis, keys, [
            source_uid, int(recent)])


class MessageUpdate(ScriptBase[bytes]):

    def __init__(self) -> None:
        super().__init__('message_update')

    async def __call__(self, redis: Redis, mbx_keys: MailboxKeys, *,
                       uid: int, flags: Sequence[str], mode: bytes) -> bytes:
        keys = [mbx_keys.uids, mbx_keys.changes, mbx_keys.deleted,
                mbx_keys.unseen]
        return await self.eval(redis, keys, [
            uid, mode, self._json(flags)])


class MessageDelete(ScriptBase[None]):

    def __init__(self) -> None:
        super().__init__('message_delete')

    async def __call__(self, redis: Redis,
                       mbx_keys: MailboxKeys, cl_keys: CleanupKeys, *,
                       uids: Sequence[int]) -> None:
        keys = [mbx_keys.uids, mbx_keys.seq, mbx_keys.content,
                mbx_keys.changes, mbx_keys.recent, mbx_keys.deleted,
                mbx_keys.unseen, cl_keys.contents]
        return await self.eval(redis, keys, [
            self._json(uids),
            mbx_keys.root.named['namespace'],
            mbx_keys.root.named['mailbox_id']])


class MailboxSnapshot(ScriptBase[Tuple[int, int, int, int, Optional[int]]]):

    def __init__(self) -> None:
        super().__init__('mailbox_snapshot')

    def _convert(self, ret: Tuple[bytes, bytes, bytes, bytes, bytes]) \
            -> Tuple[int, int, int, int, Optional[int]]:
        return (int(ret[0]), int(ret[1]), int(ret[2]),
                int(ret[3]), self._maybe_int(ret[4]))

    async def __call__(self, redis: Redis, mbx_keys: MailboxKeys) \
            -> Tuple[int, int, int, int, Optional[int]]:
        keys = [mbx_keys.max_uid, mbx_keys.uids, mbx_keys.seq,
                mbx_keys.recent, mbx_keys.unseen]
        return await self.eval(redis, keys, [])


class MailboxList(ScriptBase[Sequence[bytes]]):

    def __init__(self) -> None:
        super().__init__('mailbox_list')

    def _convert(self, ret: Tuple[Mapping[bytes, bytes], Sequence[bytes]]) \
            -> Sequence[bytes]:
        mailboxes, mbx_order = ret
        mailboxes_iter = iter(mailboxes)
        mailboxes_zip = zip(mailboxes_iter, mailboxes_iter)
        rev_mbx = {mbx_id: key for key, mbx_id in mailboxes_zip}
        return [rev_mbx[mbx_id] for mbx_id in mbx_order if mbx_id in rev_mbx]

    async def __call__(self, redis: Redis, ns_keys: NamespaceKeys) \
            -> Sequence[bytes]:
        keys = [ns_keys.mailboxes, ns_keys.order]
        return await self.eval(redis, keys, [])


class MailboxGet(ScriptBase[Tuple[bytes, int]]):

    def __init__(self) -> None:
        super().__init__('mailbox_get')

    def _convert(self, ret: Tuple[bytes, bytes]) -> Tuple[bytes, int]:
        return (ret[0], int(ret[1]))

    async def __call__(self, redis: Redis, ns_keys: NamespaceKeys, *,
                       name: bytes) -> Tuple[bytes, int]:
        keys = [ns_keys.mailboxes, ns_keys.uid_validity]
        return await self.eval(redis, keys, [name])


class MailboxAdd(ScriptBase[None]):

    def __init__(self) -> None:
        super().__init__('mailbox_add')

    async def __call__(self, redis: Redis, ns_keys: NamespaceKeys, *,
                       name: bytes, mailbox_id: bytes) -> None:
        keys = [ns_keys.mailboxes, ns_keys.order, ns_keys.max_order,
                ns_keys.uid_validity]
        return await self.eval(redis, keys, [name, mailbox_id])


class MailboxDelete(ScriptBase[None]):

    def __init__(self) -> None:
        super().__init__('mailbox_delete')

    async def __call__(self, redis: Redis,
                       ns_keys: NamespaceKeys, cl_keys: CleanupKeys, *,
                       name: bytes) -> None:
        keys = [ns_keys.mailboxes, ns_keys.order, cl_keys.mailboxes]
        return await self.eval(redis, keys, [
            name,
            ns_keys.root.named['namespace']])
