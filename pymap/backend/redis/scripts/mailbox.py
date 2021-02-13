
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Final, Optional

from aioredis import Redis

from . import ScriptBase
from ..keys import CleanupKeys, NamespaceKeys, ContentKeys, MailboxKeys

__all__ = ['MailboxScripts']


class MailboxScripts:

    def __init__(self) -> None:
        super().__init__()
        self.add: Final = MessageAdd()
        self.copy: Final = MessageCopy()
        self.move: Final = MessageMove()
        self.update: Final = MessageUpdate()
        self.delete: Final = MessageDelete()
        self.snapshot: Final = MailboxSnapshot()


class MessageAdd(ScriptBase[tuple[int, bytes, bytes]]):

    def __init__(self) -> None:
        super().__init__('message_add')

    def _convert(self, ret: tuple[bytes, bytes, bytes]) \
            -> tuple[int, bytes, bytes]:
        return (int(ret[0]), ret[1], ret[2])

    async def __call__(self, redis: Redis, ns_keys: NamespaceKeys,
                       ct_keys: ContentKeys, mbx_keys: MailboxKeys, *,
                       recent: bool, date: bytes, flags: Sequence[str],
                       email_id: bytes, thread_id: bytes,
                       thread_keys: Sequence[str],
                       message: bytes, message_json: Mapping[str, Any],
                       header: bytes, header_json: Mapping[str, Any]) \
            -> tuple[int, bytes, bytes]:
        keys = [mbx_keys.max_uid, mbx_keys.uids, mbx_keys.seq,
                mbx_keys.content, mbx_keys.changes, mbx_keys.recent,
                mbx_keys.deleted, mbx_keys.unseen,
                ns_keys.max_modseq, ns_keys.thread_keys,
                ns_keys.content_refs, ct_keys.data]
        return await self.eval(redis, keys, [
            int(recent), self._pack(flags), date,
            email_id, thread_id, self._pack(thread_keys),
            message, self._pack(message_json),
            header, self._pack(header_json)])


class MessageCopy(ScriptBase[int]):

    def __init__(self) -> None:
        super().__init__('message_copy')

    def _convert(self, ret: tuple[bytes]) -> int:
        return int(ret[0])

    async def __call__(self, redis: Redis, ns_keys: NamespaceKeys,
                       mbx_keys: MailboxKeys, dest_mbx_keys: MailboxKeys, *,
                       source_uid: int, recent: bool) -> int:
        keys = [mbx_keys.uids, dest_mbx_keys.max_uid, dest_mbx_keys.uids,
                dest_mbx_keys.seq, dest_mbx_keys.content,
                dest_mbx_keys.changes, dest_mbx_keys.recent,
                dest_mbx_keys.deleted, dest_mbx_keys.unseen,
                ns_keys.max_modseq, ns_keys.content_refs]
        return await self.eval(redis, keys, [
            source_uid, int(recent)])


class MessageMove(ScriptBase[int]):

    def __init__(self) -> None:
        super().__init__('message_move')

    def _convert(self, ret: tuple[bytes]) -> int:
        return int(ret[0])

    async def __call__(self, redis: Redis, ns_keys: NamespaceKeys,
                       mbx_keys: MailboxKeys, dest_mbx_keys: MailboxKeys, *,
                       source_uid: int, recent: bool) -> int:
        keys = [mbx_keys.uids, mbx_keys.seq, mbx_keys.content,
                mbx_keys.changes, mbx_keys.recent, mbx_keys.deleted,
                mbx_keys.unseen, dest_mbx_keys.max_uid, dest_mbx_keys.uids,
                dest_mbx_keys.seq, dest_mbx_keys.content,
                dest_mbx_keys.changes, dest_mbx_keys.recent,
                dest_mbx_keys.deleted, dest_mbx_keys.unseen,
                ns_keys.max_modseq]
        return await self.eval(redis, keys, [
            source_uid, int(recent)])


class MessageUpdate(ScriptBase[bytes]):

    def __init__(self) -> None:
        super().__init__('message_update')

    async def __call__(self, redis: Redis,
                       ns_keys: NamespaceKeys, mbx_keys: MailboxKeys, *,
                       uid: int, flags: Sequence[str], mode: bytes) -> bytes:
        keys = [mbx_keys.uids, mbx_keys.changes, mbx_keys.deleted,
                mbx_keys.unseen, ns_keys.max_modseq]
        return await self.eval(redis, keys, [
            uid, mode, self._pack(flags)])


class MessageDelete(ScriptBase[None]):

    def __init__(self) -> None:
        super().__init__('message_delete')

    async def __call__(self, redis: Redis, ns_keys: NamespaceKeys,
                       mbx_keys: MailboxKeys, cl_keys: CleanupKeys, *,
                       uids: Sequence[int]) -> None:
        keys = [mbx_keys.uids, mbx_keys.seq, mbx_keys.content,
                mbx_keys.changes, mbx_keys.recent, mbx_keys.deleted,
                mbx_keys.unseen, ns_keys.max_modseq, cl_keys.contents]
        return await self.eval(redis, keys, [
            self._pack(uids),
            mbx_keys.root.named['namespace'],
            mbx_keys.root.named['mailbox_id']])


class MailboxSnapshot(ScriptBase[tuple[int, int, int, int, Optional[int]]]):

    def __init__(self) -> None:
        super().__init__('mailbox_snapshot')

    def _convert(self, ret: tuple[bytes, bytes, bytes, bytes, bytes]) \
            -> tuple[int, int, int, int, Optional[int]]:
        return (int(ret[0]), int(ret[1]), int(ret[2]),
                int(ret[3]), self._maybe_int(ret[4]))

    async def __call__(self, redis: Redis, mbx_keys: MailboxKeys) \
            -> tuple[int, int, int, int, Optional[int]]:
        keys = [mbx_keys.max_uid, mbx_keys.uids, mbx_keys.seq,
                mbx_keys.recent, mbx_keys.unseen]
        return await self.eval(redis, keys, [])
