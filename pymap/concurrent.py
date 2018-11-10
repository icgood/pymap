"""Implements some concurrency utilities used by pymap. Each has
an implementation using :mod:`asyncio` and :mod`threading` primitives.

"""

import asyncio
import os.path
import time
from abc import abstractmethod, ABCMeta
from asyncio import Event as _asyncio_Event, Lock as _asyncio_Lock
from concurrent.futures import TimeoutError
from contextlib import asynccontextmanager
from threading import Event as _threading_Event, Lock as _threading_Lock
from typing import AsyncContextManager, AsyncIterator, TypeVar
from weakref import WeakSet

__all__ = ['Event', 'ReadWriteLock', 'FileLock', 'TimeoutError']

_Event = TypeVar('_Event', bound='Event')


class ReadWriteLock(metaclass=ABCMeta):
    """Read-write lock."""

    @classmethod
    def for_asyncio(cls) -> 'ReadWriteLock':
        """Return a read-write lock for asyncio."""
        return _AsyncioReadWriteLock()

    @classmethod
    def for_threading(cls) -> 'ReadWriteLock':
        """Return a read-write lock for threading."""
        return _ThreadingReadWriteLock()

    @property
    @abstractmethod
    def subsystem(self) -> str:
        """The sub-system the read-write lock was created for, ``'asyncio'`` or
        ``'threading'``.

        """
        ...

    @abstractmethod
    def read_lock(self) -> AsyncContextManager[None]:
        """Acquires a read-lock, blocking until any write-locks are released.

        """
        ...

    @abstractmethod
    def write_lock(self) -> AsyncContextManager[None]:
        """Acquires a write-lock, blocking until all read- or write-locks are
        released.

        """
        ...


class Event(metaclass=ABCMeta):
    """Concurrent event, one thread signals and any waiting event is released.

    """

    @classmethod
    def for_asyncio(cls) -> 'Event':
        """Return an event for asyncio."""
        return _AsyncioEvent()

    @classmethod
    def for_threading(cls) -> 'Event':
        """Return an event for threading."""
        return _ThreadingEvent()

    @property
    @abstractmethod
    def subsystem(self) -> str:
        """The sub-system the event was created for, ``'asyncio'`` or
        ``'threading'``.

        """
        ...

    @abstractmethod
    def or_event(self: _Event, *events: _Event) -> _Event:
        """Return a new event that is signalled when either the current thread
        or any of the provided threads are signalled.

        Args:
            events: Additional threads to be signalled by.

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
    async def wait(self, timeout: float = None) -> None:
        """Wait until another thread signals.

        Args:
            timeout: The timeout in seconds.

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


class _ThreadingReadWriteLock(ReadWriteLock):

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


class FileLock(ReadWriteLock):
    """Uses the presence or absence of a file on the filesystem to simulate
    a read-write lock. If the file is present, other read- and write-locks will
    block until the file is gone. If the file is absent, read-locks will not
    block. Write-locks will create the file on acquire and remove it on
    release.

    Args:
        path: The path of the lock file.
        expiration: Lock files older than this age will be deleted.
        read_retry_delay: The delay between read-lock attempts.
        read_retry_max: Max number of read-lock retries before failure.
        write_retry_delay: The delay between write-lock attempts.
        write_retry_max: Max number of write-lock retries before failure.

    """

    def __init__(self, path: str, expiration: float = 360.0,
                 read_retry_delay: float = 0.1, read_retry_max: int = 100,
                 write_retry_delay: float = 0.1, write_retry_max: int = 100) \
            -> None:
        super().__init__()
        self.path = path
        self.expiration = expiration
        self.read_retry_delay = read_retry_delay
        self.read_retry_max = read_retry_max
        self.write_retry_delay = write_retry_delay
        self.write_retry_max = write_retry_max

    @property
    def subsystem(self) -> str:
        return 'file'

    def _check_lock(self) -> bool:
        try:
            statinfo = os.stat(self.path)
        except FileNotFoundError:
            return True
        else:
            if time.time() - statinfo.st_mtime >= self.expiration:
                try:
                    os.unlink(self.path)
                except OSError:
                    pass
                return True
            return False

    def _try_lock(self) -> bool:
        try:
            with open(self.path, 'x'):
                pass
        except FileExistsError:
            return False
        else:
            return True

    def _unlock(self) -> None:
        try:
            os.unlink(self.path)
        except OSError:
            pass

    @asynccontextmanager
    async def read_lock(self) -> AsyncIterator[None]:
        if self._check_lock():
            yield
            return
        for _ in range(self.read_retry_max):
            await asyncio.sleep(self.read_retry_delay)
            if not os.path.exists(self.path):
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
        for _ in range(self.write_retry_max):
            await asyncio.sleep(self.write_retry_delay)
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
        self._listeners: WeakSet['_AsyncioEvent'] = WeakSet()

    @property
    def subsystem(self) -> str:
        return 'asyncio'

    def or_event(self, *events: '_AsyncioEvent') -> '_AsyncioEvent':
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

    async def wait(self, timeout: float = None) -> None:
        await asyncio.wait_for(self._event.wait(), timeout=timeout)


class _ThreadingEvent(Event):

    def __init__(self) -> None:
        super().__init__()
        self._event = _threading_Event()
        self._listeners: WeakSet['_ThreadingEvent'] = WeakSet()

    @property
    def subsystem(self) -> str:
        return 'threading'

    def or_event(self, *events: '_ThreadingEvent') -> '_ThreadingEvent':
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

    async def wait(self, timeout: float = None) -> None:
        if not self._event.wait(timeout=timeout):
            raise TimeoutError()
