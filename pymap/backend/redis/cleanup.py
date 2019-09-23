
from __future__ import annotations

import asyncio
import logging
from contextlib import closing
from typing import ClassVar, Callable, Awaitable, NoReturn

from aioredis import Redis, ConnectionClosedError  # type: ignore

from .keys import GlobalKeys, CleanupKeys, NamespaceKeys, ContentKeys, \
    MailboxKeys, MessageKeys
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

    async def run_forever(self) -> NoReturn:
        """Run the cleanup loop indefinitely."""
        while True:
            try:
                with closing(await self._connect_redis()) as redis:
                    await CleanupThread(redis, self._global_keys).run()
            except (ConnectionClosedError, OSError):
                _log.warning('Redis connection failure', exc_info=True)
            await asyncio.sleep(self.connection_delay)


class CleanupThread:
    """Defines the logic for monitoring and executing cleanup of various
    entities.

    Args:
        redis: The redis connection object.
        global_keys: The global keys group.

    """

    namespace_ttl: ClassVar[int] = 0
    mailbox_ttl: ClassVar[int] = 600
    message_ttl: ClassVar[int] = 600
    content_ttl: ClassVar[int] = 3600

    def __init__(self, redis: Redis, global_keys: GlobalKeys) -> None:
        super().__init__()
        self._redis = redis
        self._global_keys = global_keys
        self._keys = keys = CleanupKeys(global_keys)
        self._order = (keys.messages, keys.mailboxes, keys.namespaces,
                       keys.contents)

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
        elif cleanup_key == keys.messages:
            namespace, mailbox_id, msg_uid = cleanup_val.split(b'\x00', 2)
            await self._run_message(namespace, mailbox_id, msg_uid)
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

    async def _run_message(self, namespace: bytes, mailbox_id: bytes,
                           msg_uid: bytes) -> None:
        ns_keys = NamespaceKeys(self._global_keys, namespace)
        mbx_keys = MailboxKeys(ns_keys, mailbox_id)
        msg_keys = MessageKeys(mbx_keys, msg_uid)
        await _scripts.message(self._redis, self._keys, mbx_keys, msg_keys,
                               ttl=self.message_ttl)

    async def _run_content(self, namespace: bytes, email_id: bytes) -> None:
        ns_keys = NamespaceKeys(self._global_keys, namespace)
        ct_keys = ContentKeys(ns_keys, email_id)
        await _scripts.content(self._redis, ct_keys,
                               ttl=self.content_ttl)
