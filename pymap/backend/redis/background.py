
from __future__ import annotations

import asyncio
import logging
import uuid
from abc import abstractmethod
from asyncio import Task, CancelledError
from contextlib import AsyncExitStack
from typing import ClassVar, Protocol

from redis.asyncio import Redis
from pymap.context import connection_exit
from pymap.health import HealthStatus

__all__ = ['BackgroundAction', 'BackgroundTask', 'NoopAction']

_log = logging.getLogger(__name__)


class BackgroundAction(Protocol):
    """An action to perform with the connection."""

    @abstractmethod
    async def __call__(self, conn: Redis[bytes], duration: float) -> None:
        ...


class NoopAction(BackgroundAction):
    """A background action that calls :meth:`~aioredis.client.Redis.blpop` on
    a randomly-generated key.

    """

    async def __call__(self, conn: Redis[bytes], duration: float) -> None:
        key = b'invalid-' + uuid.uuid4().bytes + uuid.uuid4().bytes
        duration2: int = duration  # type: ignore
        await conn.blpop(key, timeout=duration2)


class BackgroundTask:
    """Maintains a :class:`CleanupThread` for the duration of the process
    lifetime, restarting on failure.

    Args:
        address: The redis server address for mail data.
        status: The system health status.
        root: The root redis key.

    """

    #: The delay between redis reconnect attempts, on connection failure.
    connection_delay: ClassVar[float] = 5.0

    #: The duration to hold an active connection before reconnecting, to detect
    #: silent failures.
    reconnect_duration: ClassVar[float] = 30.0

    def __init__(self, redis: Redis[bytes], status: HealthStatus,
                 action: BackgroundAction) -> None:
        super().__init__()
        self._redis = redis
        self._status = status
        self._action = action

    async def _run_forever(self) -> None:
        while True:
            try:
                async with AsyncExitStack() as stack:
                    connection_exit.set(stack)
                    conn = await stack.enter_async_context(
                        self._redis.client())
                    self._status.set_healthy()
                    await self._action(conn, self.reconnect_duration)
            except OSError:
                self._status.set_unhealthy()
            except CancelledError:
                break
            await asyncio.sleep(self.connection_delay)

    def start(self) -> Task[None]:
        """Return a task running the cleanup loop indefinitely."""
        return asyncio.create_task(self._run_forever())
