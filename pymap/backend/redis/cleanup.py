
from __future__ import annotations

import asyncio
import logging
from contextlib import closing
from typing import ClassVar, Callable, Awaitable, NoReturn
from typing_extensions import Final

from aioredis import Redis, ConnectionClosedError  # type: ignore

from ._util import unwatch_pipe
from .keys import RedisKey, GlobalKeys, CleanupKeys, NamespaceKeys, \
    ContentKeys, MailboxKeys, MessageKeys

__all__ = ['Cleanup', 'CleanupTask', 'CleanupThread']

_log = logging.getLogger(__name__)


class Cleanup:
    """Defines the logic for adding key groups to be cleaned up.

    Args:
        root: The root redis key.

    """

    content_expire = 3600

    def __init__(self, global_keys: GlobalKeys) -> None:
        super().__init__()
        keys = CleanupKeys(global_keys)
        self.keys: Final = keys
        self._order = (keys.messages, keys.mailboxes, keys.namespaces,
                       keys.contents, keys.roots)

    def add_namespace(self, pipe: Redis, keys: NamespaceKeys) -> None:
        """Add the namespace to be cleaned up.

        Args:
            pipe: Piped redis commands.
            keys: The namespace key group.

        """
        cleanup_val = keys.root.named['namespace']
        pipe.rpush(self.keys.namespaces, cleanup_val)

    def add_mailbox(self, pipe: Redis, keys: MailboxKeys) -> None:
        """Add the mailbox to be cleaned up.

        Args:
            pipe: Piped redis commands.
            keys: The mailbox key group.

        """
        namespace = keys.root.named['namespace']
        mailbox_id = keys.root.named['mailbox_id']
        cleanup_val = b'%b\x00%b' % (namespace, mailbox_id)
        pipe.rpush(self.keys.mailboxes, cleanup_val)

    def add_message(self, pipe: Redis, keys: MessageKeys) -> None:
        """Add the message to be cleaned up.

        Args:
            pipe: Piped redis commands.
            keys: The message key group.

        """
        namespace = keys.root.named['namespace']
        mailbox_id = keys.root.named['mailbox_id']
        msg_uid = keys.root.named['uid']
        cleanup_val = b'%b\x00%b\x00%b' \
            % (namespace, mailbox_id, msg_uid)
        pipe.rpush(self.keys.messages, cleanup_val)

    def add_content(self, pipe: Redis, keys: ContentKeys) -> None:
        """Add the content to be cleaned up.

        Args:
            pipe: Piped redis commands.
            keys: The content key group.

        """
        namespace = keys.root.named['namespace']
        email_id = keys.root.named['email_id']
        cleanup_val = b'%b\x00%b' % (namespace, email_id)
        pipe.rpush(self.keys.contents, cleanup_val)

    def add_root(self, pipe: Redis, root: RedisKey) -> None:
        """Add the content to be cleaned up.

        Args:
            pipe: Piped redis commands.
            root: The redis key prefix.

        """
        cleanup_val = root.wildcard
        pipe.rpush(self.keys.roots, cleanup_val)


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

    def __init__(self, redis: Redis, global_keys: GlobalKeys) -> None:
        super().__init__()
        self._redis = redis
        self._cleanup = Cleanup(global_keys)
        self._global_keys = global_keys

    async def run(self) -> NoReturn:
        """Run the cleanup loop indefinitely.

        Raises:
            :class:`~aioredis.ConnectionClosedError`: The connection to redis
                was interrupted.

        """
        redis = self._redis
        cleanup = self._cleanup
        while True:
            cleanup_key, cleanup_val = await redis.blpop(
                *cleanup._order, timeout=0)
            try:
                await asyncio.shield(self._run_one(cleanup_key, cleanup_val))
            except Exception:
                _log.warning('Cleanup failed: key=%s val=%s',
                             cleanup_key, cleanup_val, exc_info=True)
                raise

    async def _run_one(self, cleanup_key: bytes, cleanup_val: bytes) -> None:
        cleanup = self._cleanup
        if cleanup_key == cleanup.keys.namespaces:
            namespace = cleanup_val
            await self._run_namespace(namespace)
        elif cleanup_key == cleanup.keys.mailboxes:
            namespace, mailbox_id = cleanup_val.split(b'\x00', 1)
            await self._run_mailbox(namespace, mailbox_id)
        elif cleanup_key == cleanup.keys.messages:
            namespace, mailbox_id, msg_uid = cleanup_val.split(b'\x00', 2)
            await self._run_message(namespace, mailbox_id, msg_uid)
        elif cleanup_key == cleanup.keys.contents:
            namespace, email_id = cleanup_val.split(b'\x00', 1)
            await self._run_content(namespace, email_id)
        elif cleanup_key == cleanup.keys.roots:
            wildcard = cleanup_val
            await self._run_root(wildcard)

    async def _run_namespace(self, namespace: bytes) -> None:
        redis = self._redis
        cleanup = self._cleanup
        ns_keys = NamespaceKeys(self._global_keys, namespace)
        pipe = unwatch_pipe(redis)
        pipe.hvals(ns_keys.mailboxes)
        _, mailbox_ids = await pipe.execute()
        multi = redis.multi_exec()
        multi.unlink(*ns_keys.keys)
        for mailbox_id in mailbox_ids:
            mbx_keys = MailboxKeys(ns_keys, mailbox_id)
            cleanup.add_mailbox(multi, mbx_keys)
        cleanup.add_root(multi, ns_keys.root)
        await multi.execute()

    async def _run_mailbox(self, namespace: bytes, mailbox_id: bytes) -> None:
        redis = self._redis
        cleanup = self._cleanup
        ns_keys = NamespaceKeys(self._global_keys, namespace)
        mbx_keys = MailboxKeys(ns_keys, mailbox_id)
        pipe = unwatch_pipe(redis)
        pipe.smembers(mbx_keys.uids)
        _, msg_uids = await pipe.execute()
        multi = redis.multi_exec()
        multi.unlink(*mbx_keys.keys)
        for msg_uid in msg_uids:
            msg_keys = MessageKeys(mbx_keys, msg_uid)
            cleanup.add_message(multi, msg_keys)
        cleanup.add_root(multi, mbx_keys.root)
        await multi.execute()

    async def _run_message(self, namespace: bytes, mailbox_id: bytes,
                           msg_uid: bytes) -> None:
        redis = self._redis
        cleanup = self._cleanup
        ns_keys = NamespaceKeys(self._global_keys, namespace)
        mbx_keys = MailboxKeys(ns_keys, mailbox_id)
        msg_keys = MessageKeys(mbx_keys, msg_uid)
        pipe = unwatch_pipe(redis)
        pipe.hget(msg_keys.immutable, b'emailid')
        _, email_id = await pipe.execute()
        multi = redis.multi_exec()
        multi.unlink(*msg_keys.keys)
        if email_id is not None:
            ct_keys = ContentKeys(ns_keys, email_id)
            cleanup.add_content(multi, ct_keys)
        cleanup.add_root(multi, msg_keys.root)
        await multi.execute()

    async def _run_content(self, namespace: bytes, email_id: bytes) -> None:
        redis = self._redis
        cleanup = self._cleanup
        ns_keys = NamespaceKeys(self._global_keys, namespace)
        ct_keys = ContentKeys(ns_keys, email_id)
        pipe = unwatch_pipe(redis)
        pipe.ttl(ct_keys.data)
        pipe.hincrby(ns_keys.content_refs, email_id, -1)
        _, ttl, refs = await pipe.execute()
        if ttl < 0 and int(refs or 0) <= 0:
            await redis.expire(ct_keys.data, cleanup.content_expire)

    async def _run_root(self, wildcard: bytes) -> None:
        redis = self._redis
        cur = b'0'
        await redis.unwatch()
        while cur:
            cur, keys = await redis.scan(cur, match=wildcard)
            if keys:
                await redis.unlink(*keys)
