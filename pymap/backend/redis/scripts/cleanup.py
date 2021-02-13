
from __future__ import annotations

from typing import Final

from aioredis import Redis

from . import ScriptBase
from ..keys import CleanupKeys, NamespaceKeys, ContentKeys, MailboxKeys

__all__ = ['CleanupScripts']


class CleanupScripts:

    def __init__(self) -> None:
        super().__init__()
        self.namespace: Final = CleanupNamespace()
        self.mailbox: Final = CleanupMailbox()
        self.content: Final = CleanupContent()


class CleanupNamespace(ScriptBase[None]):

    def __init__(self) -> None:
        super().__init__('cleanup_namespace')

    async def __call__(self, redis: Redis,
                       cl_keys: CleanupKeys, ns_keys: NamespaceKeys, *,
                       ttl: int) -> None:
        keys = [cl_keys.mailboxes, ns_keys.mailboxes, *ns_keys.keys]
        return await self.eval(redis, keys, [
            ttl, ns_keys.root.named['namespace']])


class CleanupMailbox(ScriptBase[None]):

    def __init__(self) -> None:
        super().__init__('cleanup_mailbox')

    async def __call__(self, redis: Redis,
                       cl_keys: CleanupKeys, mbx_keys: MailboxKeys, *,
                       ttl: int) -> None:
        keys = [cl_keys.contents, mbx_keys.uids, mbx_keys.content,
                *mbx_keys.keys]
        return await self.eval(redis, keys, [
            ttl, mbx_keys.root.named['namespace'],
            mbx_keys.root.named['mailbox_id']])


class CleanupContent(ScriptBase[None]):

    def __init__(self) -> None:
        super().__init__('cleanup_content')

    async def __call__(self, redis: Redis,
                       ns_keys: NamespaceKeys, ct_keys: ContentKeys, *,
                       ttl: int) -> None:
        keys = [ns_keys.content_refs, ct_keys.data]
        return await self.eval(redis, keys, [
            ttl, ct_keys.root.named['email_id']])
