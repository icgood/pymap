
from __future__ import annotations

import os
import os.path
from abc import abstractmethod, ABCMeta
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, AbstractAsyncContextManager
from tempfile import NamedTemporaryFile
from typing import TypeVar, Generic, Any, IO, Self

from pymap.concurrent import FileLock

__all__ = ['FileReadable', 'FileWriteable']

_RT = TypeVar('_RT', bound='FileReadable')
_WT = TypeVar('_WT', bound='FileWriteable')


class FileReadable(metaclass=ABCMeta):

    def __init__(self, path: str) -> None:
        super().__init__()
        self._path = path

    @property
    def path(self) -> str:
        return self._path

    @classmethod
    def get_file(cls, path: str) -> str:
        return path

    @classmethod
    def get_lock(cls, path: str) -> str | None:
        return None

    @classmethod
    @abstractmethod
    def get_default(cls, path: str) -> Self:
        ...

    @classmethod
    @abstractmethod
    def open(cls, path: str, fp: IO[str]) -> Self:
        ...

    @abstractmethod
    def read(self, fp: IO[str]) -> None:
        ...

    @classmethod
    @asynccontextmanager
    async def _noop_lock(cls) -> AsyncIterator[None]:
        yield

    @classmethod
    def read_lock(cls, path: str) -> AbstractAsyncContextManager[None]:
        lock_path = cls.get_lock(path)
        if lock_path is not None:
            return FileLock(lock_path).read_lock()
        else:
            return cls._noop_lock()

    @classmethod
    def write_lock(cls, path: str) -> AbstractAsyncContextManager[None]:
        lock_file = cls.get_lock(path)
        if lock_file is not None:
            return FileLock(lock_file).write_lock()
        else:
            return cls._noop_lock()

    @classmethod
    def file_exists(cls, path: str) -> bool:
        file_path = cls.get_file(path)
        return os.path.exists(file_path)

    @classmethod
    def file_open(cls, path: str) -> Self:
        file_path = cls.get_file(path)
        try:
            with open(file_path, 'r') as in_file:
                return cls.open(path, in_file)
        except FileNotFoundError:
            return cls.get_default(path)

    @classmethod
    def file_read(cls, path: str) -> Self:
        file_path = cls.get_file(path)
        try:
            with open(file_path, 'r') as in_file:
                ret = cls.open(path, in_file)
                ret.read(in_file)
                return ret
        except FileNotFoundError:
            return cls.get_default(path)

    @classmethod
    def with_read(cls: type[_RT], path: str) \
            -> AbstractAsyncContextManager[_RT]:
        return _FileReadWith(path, cls)


class FileWriteable(FileReadable, metaclass=ABCMeta):

    def __init__(self, path: str) -> None:
        super().__init__(path)
        self._touched = False
        self._watched = False

    @property
    @abstractmethod
    def empty(self) -> bool:
        ...

    @property
    def touched(self) -> bool:
        return self._touched

    def touch(self) -> None:
        if self._watched:
            self._touched = True

    @abstractmethod
    def write(self, fp: IO[str]) -> None:
        ...

    def file_delete(self) -> None:
        file_path = self.get_file(self.path)
        os.remove(file_path)
        self._touched = False

    def file_write(self) -> None:
        file_path = self.get_file(self.path)
        with NamedTemporaryFile('w', delete=False) as tmp:
            self.write(tmp)
        os.rename(tmp.name, file_path)
        self._touched = False

    @classmethod
    def with_init(cls: type[_WT], path: str) \
            -> AbstractAsyncContextManager[_WT]:
        return _FileInitWith(path, cls)

    @classmethod
    def with_write(cls: type[_WT], path: str) \
            -> AbstractAsyncContextManager[_WT]:
        return _FileWriteWith(path, cls)


class _FileReadWith(Generic[_RT]):

    def __init__(self, path: str, cls: type[_RT]) -> None:
        super().__init__()
        self._path = path
        self._cls = cls
        self._obj: _RT | None = None

    async def __aenter__(self) -> _RT:
        path = self._path
        cls = self._cls
        async with cls.read_lock(path):
            self._obj = obj = cls.file_read(path)
        return obj

    async def __aexit__(self, exc_type: Any, exc_val: Any,
                        exc_tb: Any) -> bool:
        return False


class _FileInitWith(Generic[_WT]):

    def __init__(self, path: str, cls: type[_WT]) -> None:
        super().__init__()
        self._path = path
        self._cls = cls
        self._obj: _WT | None = None

    async def __aenter__(self) -> _WT:
        path = self._path
        cls = self._cls
        if cls.file_exists(path):
            async with cls.read_lock(path):
                self._obj = obj = cls.file_open(path)
        else:
            async with cls.write_lock(path):
                self._obj = obj = cls.file_open(path)
                obj.file_write()
        return obj

    async def __aexit__(self, exc_type: Any, exc_val: Any,
                        exc_tb: Any) -> bool:
        return False


class _FileWriteWith(Generic[_WT]):

    def __init__(self, path: str, cls: type[_WT]) -> None:
        super().__init__()
        self._path = path
        self._cls = cls
        self._exists = False
        self._lock: AbstractAsyncContextManager[None] | None = None
        self._obj: _WT | None = None

    async def _acquire_lock(self) -> None:
        self._lock = self._cls.write_lock(self._path)
        await self._lock.__aenter__()

    async def _release_lock(self) -> None:
        lock = self._lock
        if not lock:
            raise RuntimeError()  # Lock not acquired.
        await lock.__aexit__(None, None, None)

    async def __aenter__(self) -> _WT:
        path = self._path
        cls = self._cls
        await self._acquire_lock()
        self._exists = cls.file_exists(path)
        self._obj = obj = cls.file_read(path)
        obj._watched = True
        return obj

    async def __aexit__(self, exc_type: Any, exc_val: Any,
                        exc_tb: Any) -> bool:
        try:
            obj = self._obj
            if obj is None:
                raise RuntimeError()  # Context manager not entered.
            obj._watched = False
            if not exc_type and obj.touched:
                if not obj.empty:
                    obj.file_write()
                elif self._exists:
                    obj.file_delete()
            return False
        finally:
            await self._release_lock()
