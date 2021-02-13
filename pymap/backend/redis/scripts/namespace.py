
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Final

from aioredis import Redis

from . import ScriptBase
from ..keys import CleanupKeys, NamespaceKeys

__all__ = ['NamespaceScripts']


class NamespaceScripts:

    def __init__(self) -> None:
        super().__init__()
        self.list: Final = MailboxList()
        self.get: Final = MailboxGet()
        self.add: Final = MailboxAdd()
        self.delete: Final = MailboxDelete()


class MailboxList(ScriptBase[Sequence[bytes]]):

    def __init__(self) -> None:
        super().__init__('mailbox_list')

    def _convert(self, ret: tuple[Mapping[bytes, bytes], Sequence[bytes]]) \
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


class MailboxGet(ScriptBase[tuple[bytes, int]]):

    def __init__(self) -> None:
        super().__init__('mailbox_get')

    def _convert(self, ret: tuple[bytes, bytes]) -> tuple[bytes, int]:
        return (ret[0], int(ret[1]))

    async def __call__(self, redis: Redis, ns_keys: NamespaceKeys, *,
                       name: bytes) -> tuple[bytes, int]:
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
