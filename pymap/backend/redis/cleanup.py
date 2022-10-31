
from __future__ import annotations

import asyncio
import logging
import time
from typing import ClassVar

from redis.asyncio import Redis

from .background import BackgroundAction
from .keys import GlobalKeys, CleanupKeys, NamespaceKeys, ContentKeys, \
    MailboxKeys
from .scripts.cleanup import CleanupScripts

__all__ = ['CleanupAction']

_log = logging.getLogger(__name__)
_scripts = CleanupScripts()


class CleanupAction(BackgroundAction):
    """Defines the logic for monitoring and executing cleanup of various
    entities.

    Args:
        address: The redis server address.
        redis: The redis connection object.
        global_keys: The global keys group.

    """

    namespace_ttl: ClassVar[int] = 0
    mailbox_ttl: ClassVar[int] = 600
    content_ttl: ClassVar[int] = 3600

    def __init__(self, global_keys: GlobalKeys) -> None:
        super().__init__()
        self._global_keys = global_keys
        self._keys = keys = CleanupKeys(global_keys)
        self._order = (keys.mailboxes, keys.namespaces, keys.contents)

    async def __call__(self, conn: Redis[bytes], duration: float) -> None:
        now = time.time()
        finished = now + duration
        while now < finished:
            timeout: int = finished - now  # type: ignore
            cleanup = await conn.blpop(self._order, timeout=timeout)
            if cleanup is None:
                continue
            cleanup_key, cleanup_val = cleanup
            try:
                await asyncio.shield(
                    self._run_one(conn, cleanup_key, cleanup_val))
            except Exception:
                _log.warning('Cleanup failed: key=%s val=%s',
                             cleanup_key, cleanup_val, exc_info=True)
                raise
            now = time.time()

    async def _run_one(self, conn: Redis[bytes], cleanup_key: bytes,
                       cleanup_val: bytes) -> None:
        keys = self._keys
        if cleanup_key == keys.namespaces:
            namespace = cleanup_val
            await self._run_namespace(conn, namespace)
        elif cleanup_key == keys.mailboxes:
            namespace, mailbox_id = cleanup_val.split(b'\x00', 1)
            await self._run_mailbox(conn, namespace, mailbox_id)
        elif cleanup_key == keys.contents:
            namespace, email_id = cleanup_val.split(b'\x00', 1)
            await self._run_content(conn, namespace, email_id)

    async def _run_namespace(self, conn: Redis[bytes],
                             namespace: bytes) -> None:
        ns_keys = NamespaceKeys(self._global_keys, namespace)
        await _scripts.namespace(conn, self._keys, ns_keys,
                                 ttl=self.namespace_ttl)

    async def _run_mailbox(self, conn: Redis[bytes], namespace: bytes,
                           mailbox_id: bytes) -> None:
        ns_keys = NamespaceKeys(self._global_keys, namespace)
        mbx_keys = MailboxKeys(ns_keys, mailbox_id)
        await _scripts.mailbox(conn, self._keys, mbx_keys,
                               ttl=self.mailbox_ttl)

    async def _run_content(self, conn: Redis[bytes], namespace: bytes,
                           email_id: bytes) -> None:
        ns_keys = NamespaceKeys(self._global_keys, namespace)
        ct_keys = ContentKeys(ns_keys, email_id)
        await _scripts.content(conn, ns_keys, ct_keys,
                               ttl=self.content_ttl)
