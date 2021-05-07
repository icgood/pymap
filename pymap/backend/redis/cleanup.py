
from __future__ import annotations

import asyncio
import logging
from asyncio import Task
from collections.abc import Awaitable, Callable
from contextlib import AsyncExitStack
from typing import ClassVar, NoReturn

from aioredis import Redis, ConnectionClosedError
from pymap.context import connection_exit

from .keys import GlobalKeys, CleanupKeys, NamespaceKeys, ContentKeys, \
    MailboxKeys
from .scripts.cleanup import CleanupScripts

__all__ = ['CleanupTask', 'CleanupThread']

_log = logging.getLogger(__name__)
_scripts = CleanupScripts()


class CleanupTask:
    """Maintains a :class:`CleanupThread` for the duration of the process
    lifetime, restarting on failure.

    Args:
        connect_redis: Supplies a connected redis object.
        root: The root redis key.

    """

    #: The delay between redis reconnect attempts, on connection failure.
    connection_delay: ClassVar[float] = 5.0

    def __init__(self, connect_redis: Callable[[], Awaitable[Redis]],
                 global_keys: GlobalKeys) -> None:
        super().__init__()
        self._connect_redis = connect_redis
        self._global_keys = global_keys

    async def _run_forever(self) -> NoReturn:
        while True:
            try:
                async with AsyncExitStack() as stack:
                    connection_exit.set(stack)
                    redis = await self._connect_redis()
                    await CleanupThread(redis, self._global_keys).run()
            except (ConnectionClosedError, OSError):
                pass
            await asyncio.sleep(self.connection_delay)

    def start(self) -> Task[NoReturn]:
        """Return a task running the cleanup loop indefinitely."""
        return asyncio.create_task(self._run_forever())


class CleanupThread:
    """Defines the logic for monitoring and executing cleanup of various
    entities.

    Args:
        redis: The redis connection object.
        global_keys: The global keys group.

    """

    namespace_ttl: ClassVar[int] = 0
    mailbox_ttl: ClassVar[int] = 600
    content_ttl: ClassVar[int] = 3600

    def __init__(self, redis: Redis, global_keys: GlobalKeys) -> None:
        super().__init__()
        self._redis = redis
        self._global_keys = global_keys
        self._keys = keys = CleanupKeys(global_keys)
        self._order = (keys.mailboxes, keys.namespaces, keys.contents)

    async def run(self) -> NoReturn:
        """Run the cleanup loop indefinitely.

        Raises:
            :class:`~aioredis.ConnectionClosedError`: The connection to redis
                was interrupted.

        """
        redis = self._redis
        while True:
            await redis.unwatch()
            cleanup_key, cleanup_val = await redis.blpop(
                *self._order, timeout=0)
            try:
                await asyncio.shield(self._run_one(cleanup_key, cleanup_val))
            except Exception:
                _log.warning('Cleanup failed: key=%s val=%s',
                             cleanup_key, cleanup_val, exc_info=True)
                raise

    async def _run_one(self, cleanup_key: bytes, cleanup_val: bytes) -> None:
        keys = self._keys
        if cleanup_key == keys.namespaces:
            namespace = cleanup_val
            await self._run_namespace(namespace)
        elif cleanup_key == keys.mailboxes:
            namespace, mailbox_id = cleanup_val.split(b'\x00', 1)
            await self._run_mailbox(namespace, mailbox_id)
        elif cleanup_key == keys.contents:
            namespace, email_id = cleanup_val.split(b'\x00', 1)
            await self._run_content(namespace, email_id)

    async def _run_namespace(self, namespace: bytes) -> None:
        ns_keys = NamespaceKeys(self._global_keys, namespace)
        await _scripts.namespace(self._redis, self._keys, ns_keys,
                                 ttl=self.namespace_ttl)

    async def _run_mailbox(self, namespace: bytes, mailbox_id: bytes) -> None:
        ns_keys = NamespaceKeys(self._global_keys, namespace)
        mbx_keys = MailboxKeys(ns_keys, mailbox_id)
        await _scripts.mailbox(self._redis, self._keys, mbx_keys,
                               ttl=self.mailbox_ttl)

    async def _run_content(self, namespace: bytes, email_id: bytes) -> None:
        ns_keys = NamespaceKeys(self._global_keys, namespace)
        ct_keys = ContentKeys(ns_keys, email_id)
        await _scripts.content(self._redis, ns_keys, ct_keys,
                               ttl=self.content_ttl)
