"""Implements some concurrency utilities used by pymap. Each has
an implementation using :mod:`asyncio` and :mod:`threading` concurrency
primitives.

"""

from __future__ import annotations

import asyncio
import os.path
import time
from abc import abstractmethod, ABCMeta
from asyncio import Event as _asyncio_Event, Lock as _asyncio_Lock, \
    TimeoutError
from collections.abc import Awaitable, MutableSet, Sequence, AsyncIterator
from concurrent.futures import Executor, ThreadPoolExecutor
from contextlib import asynccontextmanager, AbstractAsyncContextManager
from contextvars import copy_context, Context
from threading import local, Event as _threading_Event, Lock as _threading_Lock
from typing import cast, TypeVar, Optional
from weakref import WeakSet

__all__ = ['Subsystem', 'Event', 'ReadWriteLock', 'FileLock', 'EventT', 'RetT']

#: Type variable with an upper bound of :class:`Event`.
EventT = TypeVar('EventT', bound='Event')

#: Type variable for any return type.
RetT = TypeVar('RetT')

_Delay = Sequence[float]


class Subsystem(metaclass=ABCMeta):
    """Utility for creating concurrency primitives for a subsystem, either
    :mod:`asyncio` or :mod:`threading`.

    """

    @classmethod
    def for_executor(cls, executor: Optional[Executor]) -> Subsystem:
        """Return a subsystem based on the given executor. If ``executor`` is
        None, use :mod:`asyncio`. If ``executor`` is a
        :class:`concurrent.futures.ThreadPoolExecutor`, use :mod:`threading`.

        Args:
            executor: The executor in use, if any.

        """
        if isinstance(executor, ThreadPoolExecutor):
            return _ThreadingSubsystem(executor)
        elif executor is None:
            return _AsyncioSubsystem()
        else:
            raise TypeError(executor)

    @classmethod
    def for_asyncio(cls) -> Subsystem:
        """Return a subsystem for :mod:`asyncio`."""
        return _AsyncioSubsystem()

    @classmethod
    def for_threading(cls, executor: ThreadPoolExecutor) -> Subsystem:
        """Return a subsystem for :mod:`threading`."""
        return _ThreadingSubsystem(executor)

    @property
    @abstractmethod
    def subsystem(self) -> str:
        """The subsystem name, ``'asyncio'`` or ``'threading'``."""
        ...

    @abstractmethod
    def execute(self, future: Awaitable[RetT]) -> Awaitable[RetT]:
        """Executes the future and returns its result in the subsystem. For
        :mod:`asyncio`, this simply means ``return await future``. For
        :mod:`threading`, it uses
        :meth:`~asyncio.AbstractEventLoop.run_in_executor` to run the future in
        another thread.

        Args:
            future: An awaitable result to execute by the subsystem.

        """
        ...

    @abstractmethod
    def new_rwlock(self) -> ReadWriteLock:
        """Return a new read-write lock."""
        ...

    @abstractmethod
    def new_event(self) -> Event:
        """Return a new concurrent event."""
        ...


class _AsyncioSubsystem(Subsystem):

    @property
    def subsystem(self) -> str:
        return 'asyncio'

    def execute(self, future: Awaitable[RetT]) -> Awaitable[RetT]:
        return future

    def new_rwlock(self) -> _AsyncioReadWriteLock:
        return _AsyncioReadWriteLock()

    def new_event(self) -> _AsyncioEvent:
        return _AsyncioEvent()


class _ThreadingSubsystem(Subsystem):  # pragma: no cover

    class _EventLoopLocal(local):

        def __init__(self) -> None:
            self.event_loop = asyncio.new_event_loop()

    def __init__(self, executor: ThreadPoolExecutor) -> None:
        super().__init__()
        self._local = self._EventLoopLocal()
        self._executor = executor

    @property
    def subsystem(self) -> str:
        return 'threading'

    async def execute(self, future: Awaitable[RetT]) -> RetT:
        loop = asyncio.get_event_loop()
        ctx = copy_context()
        return await loop.run_in_executor(
            self._executor, self._run_in_thread, future, ctx)

    def _run_in_thread(self, future: Awaitable[RetT], ctx: Context) -> RetT:
        loop = self._local.event_loop
        ret = ctx.run(loop.run_until_complete, future)
        return cast(RetT, ret)

    def new_rwlock(self) -> _ThreadingReadWriteLock:
        return _ThreadingReadWriteLock()

    def new_event(self) -> _ThreadingEvent:
        return _ThreadingEvent()


class ReadWriteLock(metaclass=ABCMeta):
    """Read-write lock."""

    @classmethod
    def for_asyncio(cls) -> ReadWriteLock:
        """Return a read-write lock for asyncio."""
        return _AsyncioReadWriteLock()

    @classmethod
    def for_threading(cls) -> ReadWriteLock:
        """Return a read-write lock for threading."""
        return _ThreadingReadWriteLock()

    @property
    @abstractmethod
    def subsystem(self) -> str:
        """The subsystem the read-write lock was created for, ``'asyncio'`` or
        ``'threading'``.

        """
        ...

    @abstractmethod
    def read_lock(self) -> AbstractAsyncContextManager[None]:
        """Acquires a read-lock, blocking until any write-locks are released.

        """
        ...

    @abstractmethod
    def write_lock(self) -> AbstractAsyncContextManager[None]:
        """Acquires a write-lock, blocking until all read- or write-locks are
        released.

        """
        ...


class Event(metaclass=ABCMeta):
    """Concurrent event, one thread signals and any waiting event is released.

    """

    @classmethod
    def for_asyncio(cls) -> Event:
        """Return an event for asyncio."""
        return _AsyncioEvent()

    @classmethod
    def for_threading(cls) -> Event:
        """Return an event for threading."""
        return _ThreadingEvent()

    @property
    @abstractmethod
    def subsystem(self) -> str:
        """The subsystem the event was created for, ``'asyncio'`` or
        ``'threading'``.

        """
        ...

    @abstractmethod
    def or_event(self: EventT, *events: EventT) -> EventT:
        """Return a new event that is signalled when either the current event
        or any of the provided events are signalled.

        """
        ...

    @abstractmethod
    def is_set(self) -> bool:
        """Return True if the event is set."""
        ...

    @abstractmethod
    def set(self) -> None:
        """Signal the waiting threads to release."""
        ...

    @abstractmethod
    def clear(self) -> None:
        """Clear the signal, allowing threads to wait again."""
        ...

    @abstractmethod
    async def wait(self, *, timeout: float = None) -> None:
        """Wait until another thread signals the event.

        Args:
            timeout: Maximum time to wait, in seconds.

        """
        ...


class _AsyncioReadWriteLock(ReadWriteLock):

    def __init__(self) -> None:
        super().__init__()
        self._read_lock = _asyncio_Lock()
        self._write_lock = _asyncio_Lock()
        self._counter = 0

    @property
    def subsystem(self) -> str:
        return 'asyncio'

    async def _acquire_read(self) -> bool:
        async with self._read_lock:
            self._counter += 1
            return self._counter == 1

    async def _release_read(self) -> bool:
        async with self._read_lock:
            self._counter -= 1
            return self._counter == 0

    @asynccontextmanager
    async def read_lock(self) -> AsyncIterator[None]:
        if await self._acquire_read():
            await self._write_lock.acquire()
        try:
            yield
        finally:
            if await self._release_read():
                self._write_lock.release()

    @asynccontextmanager
    async def write_lock(self) -> AsyncIterator[None]:
        async with self._write_lock:
            yield


class _ThreadingReadWriteLock(ReadWriteLock):  # pragma: no cover

    def __init__(self) -> None:
        super().__init__()
        self._read_lock = _threading_Lock()
        self._write_lock = _threading_Lock()
        self._counter = 0

    @property
    def subsystem(self) -> str:
        return 'threading'

    def _acquire_read(self) -> bool:
        with self._read_lock:
            self._counter += 1
            return self._counter == 1

    def _release_read(self) -> bool:
        with self._read_lock:
            self._counter -= 1
            return self._counter == 0

    @asynccontextmanager
    async def read_lock(self) -> AsyncIterator[None]:
        if self._acquire_read():
            self._write_lock.acquire()
        try:
            yield
        finally:
            if self._release_read():
                self._write_lock.release()

    @asynccontextmanager
    async def write_lock(self) -> AsyncIterator[None]:
        with self._write_lock:
            yield


class FileLock(ReadWriteLock):  # pragma: no cover
    """Uses the presence or absence of a file on the filesystem to simulate
    a read-write lock. If the file is present, other read- and write-locks will
    block until the file is gone. If the file is absent, read-locks will not
    block. Write-locks will create the file on acquire and remove it on
    release.

    The delay arguments are a sequence of floats used as the duration of
    successive :func:`~asyncio.sleep` calls. If this sequence is exhausted
    before a lock is established, :class:`~asyncio.TimeoutError` is thrown.

    Args:
        path: The path of the lock file.
        expiration: Lock files older than this age will be deleted.
        read_retry_delay: The delay sequence between read-lock attempts.
        write_retry_delay: The delay sequence between write-lock attempts.

    """

    _DEFAULT_DELAY = (0.01, 0.03, 0.06, 0.1, 0.15, 0.25, 0.4, 0.5, 0.5, 1.0,
                      1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0)

    def __init__(self, path: str, expiration: float = 600.0,
                 read_retry_delay: _Delay = _DEFAULT_DELAY,
                 write_retry_delay: _Delay = _DEFAULT_DELAY) \
            -> None:
        super().__init__()
        self._path = path
        self._expiration = expiration
        self._read_retry_delay = read_retry_delay
        self._write_retry_delay = write_retry_delay

    @property
    def subsystem(self) -> str:
        """The subsystem the read-write lock was created for, ``'file'``."""
        return 'file'

    def _check_lock(self) -> bool:
        try:
            statinfo = os.stat(self._path)
        except FileNotFoundError:
            return True
        else:
            if time.time() - statinfo.st_mtime >= self._expiration:
                try:
                    os.unlink(self._path)
                except OSError:
                    pass
                return True
            return False

    def _try_lock(self) -> bool:
        try:
            with open(self._path, 'x'):
                pass
        except FileExistsError:
            return False
        else:
            return True

    def _unlock(self) -> None:
        try:
            os.unlink(self._path)
        except OSError:
            pass

    @asynccontextmanager
    async def read_lock(self) -> AsyncIterator[None]:
        if self._check_lock():
            yield
            return
        for delay in self._read_retry_delay:
            await asyncio.sleep(delay)
            if not os.path.exists(self._path):
                yield
                break
        else:
            raise TimeoutError()

    @asynccontextmanager
    async def write_lock(self) -> AsyncIterator[None]:
        if self._check_lock() and self._try_lock():
            try:
                yield
            finally:
                self._unlock()
            return
        for delay in self._write_retry_delay:
            await asyncio.sleep(delay)
            if self._try_lock():
                try:
                    yield
                finally:
                    self._unlock()
                break
        else:
            raise TimeoutError()


class _AsyncioEvent(Event):

    def __init__(self) -> None:
        super().__init__()
        self._event = _asyncio_Event()
        self._listeners: MutableSet[_AsyncioEvent] = WeakSet()

    @property
    def subsystem(self) -> str:
        return 'asyncio'

    def or_event(self, *events: _AsyncioEvent) -> _AsyncioEvent:
        or_event = _AsyncioEvent()
        self._listeners.add(or_event)
        for event in events:
            event._listeners.add(or_event)
        return or_event

    def is_set(self) -> bool:
        return self._event.is_set()

    def set(self) -> None:
        self._event.set()
        for listener in self._listeners:
            listener.set()

    def clear(self) -> None:
        self._event.clear()

    async def wait(self, *, timeout: float = None) -> None:
        task = asyncio.create_task(self._event.wait())
        try:
            await asyncio.wait_for(task, timeout)
        except TimeoutError:
            pass


class _ThreadingEvent(Event):  # pragma: no cover

    def __init__(self) -> None:
        super().__init__()
        self._event = _threading_Event()
        self._listeners: MutableSet[_ThreadingEvent] = WeakSet()

    @property
    def subsystem(self) -> str:
        return 'threading'

    def or_event(self, *events: _ThreadingEvent) -> _ThreadingEvent:
        or_event = _ThreadingEvent()
        self._listeners.add(or_event)
        for event in events:
            event._listeners.add(or_event)
        return or_event

    def is_set(self) -> bool:
        return self._event.is_set()

    def set(self) -> None:
        self._event.set()
        for listener in self._listeners:
            listener.set()

    def clear(self) -> None:
        self._event.clear()

    async def wait(self, *, timeout: float = None) -> None:
        self._event.wait(timeout=timeout)
