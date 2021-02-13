
from __future__ import annotations

import os
import os.path
from abc import abstractmethod, ABCMeta
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, AbstractAsyncContextManager
from tempfile import NamedTemporaryFile
from typing import TypeVar, Generic, Optional, IO

from pymap.concurrent import FileLock

__all__ = ['NoChanges', 'FileReadable', 'FileWriteable']

_RT = TypeVar('_RT', bound='FileReadable')
_WT = TypeVar('_WT', bound='FileWriteable')


class NoChanges(Exception):
    pass


class FileReadable(metaclass=ABCMeta):

    @classmethod
    @abstractmethod
    def get_file(cls) -> str:
        ...

    @classmethod
    def get_lock(cls) -> Optional[str]:
        return None

    @classmethod
    @abstractmethod
    def get_default(cls: type[_RT], base_dir: str) -> _RT:
        ...

    @classmethod
    @abstractmethod
    def open(cls: type[_RT], base_dir: str, fp: IO[str]) -> _RT:
        ...

    def read(self, fp: IO[str]) -> None:
        pass

    @classmethod
    @asynccontextmanager
    async def _noop_lock(cls) -> AsyncIterator[None]:
        yield

    @classmethod
    def read_lock(cls, base_dir: str) -> AbstractAsyncContextManager[None]:
        lock_file = cls.get_lock()
        if lock_file:
            path = os.path.join(base_dir, lock_file)
            return FileLock(path).read_lock()
        else:
            return cls._noop_lock()

    @classmethod
    def write_lock(cls, base_dir: str) -> AbstractAsyncContextManager[None]:
        lock_file = cls.get_lock()
        if lock_file:
            path = os.path.join(base_dir, lock_file)
            return FileLock(path).write_lock()
        else:
            return cls._noop_lock()

    @classmethod
    def file_exists(cls, base_dir: str) -> bool:
        path = os.path.join(base_dir, cls.get_file())
        return os.path.exists(path)

    @classmethod
    def file_open(cls: type[_RT], base_dir: str) -> _RT:
        path = os.path.join(base_dir, cls.get_file())
        try:
            with open(path, 'r') as in_file:
                return cls.open(base_dir, in_file)
        except FileNotFoundError:
            return cls.get_default(base_dir)

    @classmethod
    def file_read(cls: type[_RT], base_dir: str) -> _RT:
        path = os.path.join(base_dir, cls.get_file())
        try:
            with open(path, 'r') as in_file:
                ret = cls.open(base_dir, in_file)
                ret.read(in_file)
                return ret
        except FileNotFoundError:
            return cls.get_default(base_dir)

    @classmethod
    def with_open(cls: type[_RT], base_dir: str) -> _FileReadWith[_RT]:
        return _FileReadWith(base_dir, cls, True)

    @classmethod
    def with_read(cls: type[_RT], base_dir: str) -> _FileReadWith[_RT]:
        return _FileReadWith(base_dir, cls, False)


class FileWriteable(FileReadable, metaclass=ABCMeta):

    @abstractmethod
    def get_dir(self) -> str:
        ...

    @abstractmethod
    def write(self, fp: IO[str]) -> None:
        ...

    @classmethod
    def delete(cls, base_dir: str) -> None:
        path = os.path.join(base_dir, cls.get_file())
        try:
            os.unlink(path)
        except OSError:
            pass

    def file_write(self) -> None:
        filename = self.get_file()
        base_dir = self.get_dir()
        tmp_dir = os.path.join(base_dir, 'tmp')
        path = os.path.join(base_dir, filename)
        with NamedTemporaryFile('w', dir=tmp_dir, delete=False) as tmp:
            self.write(tmp)
        tmp_path = os.path.join(base_dir, tmp.name)
        os.rename(tmp_path, path)

    @classmethod
    def with_write(cls: type[_WT], base_dir: str) -> _FileWriteWith[_WT]:
        return _FileWriteWith(base_dir, cls)


class _FileReadWith(Generic[_RT]):

    def __init__(self, base_dir: str, cls: type[_RT], only_open: bool) -> None:
        super().__init__()
        self._base_dir = base_dir
        self._cls = cls
        self._obj: Optional[_RT] = None
        self._only_open = only_open

    async def __aenter__(self) -> _RT:
        base_dir = self._base_dir
        cls = self._cls
        func = cls.file_open if self._only_open else cls.file_read
        async with cls.read_lock(base_dir):
            self._obj = obj = func(base_dir)
        return obj

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        return False


class _FileWriteWith(Generic[_WT]):

    def __init__(self, base_dir: str, cls: type[_WT]) -> None:
        super().__init__()
        self._base_dir = base_dir
        self._cls = cls
        self._exists = False
        self._lock: Optional[AbstractAsyncContextManager[None]] = None
        self._obj: Optional[_WT] = None

    async def _acquire_lock(self) -> None:
        self._lock = self._cls.write_lock(self._base_dir)
        await self._lock.__aenter__()

    async def _release_lock(self) -> None:
        lock = self._lock
        if not lock:
            raise RuntimeError()  # Lock not acquired.
        await lock.__aexit__(None, None, None)

    async def __aenter__(self) -> _WT:
        base_dir = self._base_dir
        cls = self._cls
        await self._acquire_lock()
        self._exists = cls.file_exists(base_dir)
        self._obj = obj = cls.file_read(base_dir)
        return obj

    def _write_obj(self) -> None:
        obj = self._obj
        if not obj:
            raise RuntimeError()  # Context manager not entered.
        obj.file_write()

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        try:
            if exc_type:
                if issubclass(exc_type, NoChanges):
                    if not self._exists:
                        self._write_obj()
                    return True
                else:
                    return False
            self._write_obj()
            return False
        finally:
            await self._release_lock()
