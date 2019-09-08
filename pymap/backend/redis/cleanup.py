
from __future__ import annotations

import asyncio
import logging
from typing import NoReturn
from typing_extensions import Final

from aioredis import Redis  # type: ignore

from ._util import reset
from .keys import RedisKey, CleanupKeys, NamespaceKeys, ContentKeys, \
    MailboxKeys, MessageKeys

__all__ = ['Cleanup', 'CleanupTask']

_log = logging.getLogger(__name__)


class Cleanup:
    """Defines the logic for adding key groups to be cleaned up.

    Args:
        root: The root redis key.

    """

    content_expire = 3600

    def __init__(self, root: RedisKey) -> None:
        super().__init__()
        keys = CleanupKeys(root)
        self.keys: Final = keys
        self._order = (keys.messages, keys.mailboxes, keys.namespaces,
                       keys.contents, keys.roots)

    def add_namespace(self, pipe: Redis, keys: NamespaceKeys) -> None:
        """Add the namespace to be cleaned up.

        Args:
            pipe: Piped redis commands.
            keys: The namespace key group.

        """
        cleanup_val = keys.root.args[b'namespace']
        pipe.rpush(self.keys.namespaces, cleanup_val)

    def add_mailbox(self, pipe: Redis, keys: MailboxKeys) -> None:
        """Add the mailbox to be cleaned up.

        Args:
            pipe: Piped redis commands.
            keys: The mailbox key group.

        """
        namespace = keys.root.args[b'namespace']
        mailbox_id = keys.root.args[b'mailbox_id']
        cleanup_val = b'%b\x00%b' % (namespace, mailbox_id)
        pipe.rpush(self.keys.mailboxes, cleanup_val)

    def add_message(self, pipe: Redis, keys: MessageKeys) -> None:
        """Add the message to be cleaned up.

        Args:
            pipe: Piped redis commands.
            keys: The message key group.

        """
        namespace = keys.root.args[b'namespace']
        mailbox_id = keys.root.args[b'mailbox_id']
        msg_uid = keys.root.args[b'uid']
        cleanup_val = b'%b\x00%b\x00%b' \
            % (namespace, mailbox_id, msg_uid)
        pipe.rpush(self.keys.messages, cleanup_val)

    def add_content(self, pipe: Redis, keys: ContentKeys) -> None:
        """Add the content to be cleaned up.

        Args:
            pipe: Piped redis commands.
            keys: The content key group.

        """
        namespace = keys.root.args[b'namespace']
        email_id = keys.root.args[b'email_id']
        cleanup_val = b'%b\x00%b' % (namespace, email_id)
        pipe.rpush(self.keys.contents, cleanup_val)

    def add_root(self, pipe: Redis, root: RedisKey) -> None:
        """Add the content to be cleaned up.

        Args:
            pipe: Piped redis commands.
            root: The redis key prefix.

        """
        cleanup_val = root.end()
        pipe.rpush(self.keys.roots, cleanup_val)


class CleanupTask:
    """Defines the logic for monitoring and executing cleanup of various
    entities.

    Args:
        redis: The redis connection object.
        root: The root redis key.

    """

    def __init__(self, redis: Redis, root: RedisKey) -> None:
        super().__init__()
        self._redis = redis
        self._root = root
        self._cleanup = Cleanup(root)

    async def run(self) -> NoReturn:
        """Run the cleanup loop indefinitely."""
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
            root = cleanup_val
            await self._run_root(root)

    async def _run_namespace(self, namespace: bytes) -> None:
        redis = await reset(self._redis)
        cleanup = self._cleanup
        ns_keys = NamespaceKeys(self._root, namespace)
        mailbox_ids = await redis.hvals(ns_keys.mailboxes)
        multi = redis.multi_exec()
        multi.unlink(*ns_keys.keys)
        for mailbox_id in mailbox_ids:
            mbx_keys = MailboxKeys(ns_keys.mbx_root, mailbox_id)
            cleanup.add_mailbox(multi, mbx_keys)
        cleanup.add_root(multi, ns_keys.root)
        await multi.execute()

    async def _run_mailbox(self, namespace: bytes, mailbox_id: bytes) -> None:
        redis = await reset(self._redis)
        cleanup = self._cleanup
        ns_keys = NamespaceKeys(self._root, namespace)
        mbx_keys = MailboxKeys(ns_keys.mbx_root, mailbox_id)
        msg_uids = await redis.smembers(mbx_keys.uids)
        multi = redis.multi_exec()
        multi.unlink(*mbx_keys.keys)
        for msg_uid in msg_uids:
            msg_keys = MessageKeys(mbx_keys.msg_root, msg_uid)
            cleanup.add_message(multi, msg_keys)
        cleanup.add_root(multi, mbx_keys.root)
        await multi.execute()

    async def _run_message(self, namespace: bytes, mailbox_id: bytes,
                           msg_uid: bytes) -> None:
        redis = await reset(self._redis)
        cleanup = self._cleanup
        ns_keys = NamespaceKeys(self._root, namespace)
        mbx_keys = MailboxKeys(ns_keys.mbx_root, mailbox_id)
        msg_keys = MessageKeys(mbx_keys.msg_root, msg_uid)
        email_id = await redis.get(msg_keys.email_id)
        multi = redis.multi_exec()
        multi.unlink(*msg_keys.keys)
        if email_id is not None:
            ct_keys = ContentKeys(ns_keys.content_root, email_id)
            cleanup.add_content(multi, ct_keys)
        cleanup.add_root(multi, msg_keys.root)
        await multi.execute()

    async def _run_content(self, namespace: bytes, email_id: bytes) -> None:
        redis = await reset(self._redis)
        cleanup = self._cleanup
        ns_keys = NamespaceKeys(self._root, namespace)
        ct_keys = ContentKeys(ns_keys.content_root, email_id)
        pipe = redis.pipeline()
        pipe.ttl(ct_keys.data)
        pipe.hincrby(ns_keys.content_refs, email_id, -1)
        ttl, refs = await pipe.execute()
        if ttl < 0 and int(refs or 0) <= 0:
            await redis.expire(ct_keys.data, cleanup.content_expire)

    async def _run_root(self, root: bytes) -> None:
        redis = await reset(self._redis)
        cur = b'0'
        match = root + b':*'
        while cur:
            cur, keys = await redis.scan(cur, match=match)
            if keys:
                await redis.unlink(*keys)
