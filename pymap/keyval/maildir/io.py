
import os
import os.path
from abc import abstractmethod, ABCMeta
from contextlib import asynccontextmanager
from tempfile import NamedTemporaryFile
from typing import TypeVar, Type, Generic, Optional, IO, AsyncContextManager, \
    AsyncIterator

from pymap.concurrent import FileLock

__all__ = ['NoChanges', 'FileReadable', 'FileWriteable']

_RT = TypeVar('_RT', bound='FileReadable')
_WT = TypeVar('_WT', bound='FileWriteable')


class NoChanges(Exception):
    """Raise in a :meth:`~FileWriteable.with_write` to indicate that the file
    has not changed and should not be re-written. The exception is swallowed by
    the context manager and is not re-raised.

    """
    pass


class FileReadable(metaclass=ABCMeta):
    """Defines an object that can be read in its entirety from a file."""

    @classmethod
    @abstractmethod
    def get_file(cls) -> str:
        """Return the filename of the file."""
        ...

    @classmethod
    def get_lock(cls) -> Optional[str]:
        """Return the filename of the lock file, if any."""
        return None

    @classmethod
    @abstractmethod
    def get_default(cls: Type[_RT], base_dir: str) -> _RT:
        """Return the default value, if the file does not exist.

        Args:
            base_dir: The directory of the file.

        """
        ...

    @classmethod
    @abstractmethod
    def open(cls: Type[_RT], base_dir: str, fp: IO[str]) -> _RT:
        """Defines how the object is opened from the file, reading any
        necessary data to create the object.

        Args:
            base_dir: The directory of the file.
            fp: The text file object open for reading.

        """
        ...

    def read(self, fp: IO[str]) -> None:
        """Defines how the rest of the object is read from the file,
        if applicable.

        Args:
            fp: The text file object open for reading.

        """
        pass

    @classmethod
    @asynccontextmanager
    async def _noop_lock(cls) -> AsyncIterator[None]:
        yield

    @classmethod
    def read_lock(cls, base_dir: str) -> AsyncContextManager[None]:
        """Async context manager that acquires and releases a read lock."""
        lock_file = cls.get_lock()
        if lock_file:
            path = os.path.join(base_dir, lock_file)
            return FileLock(path).read_lock()
        else:
            return cls._noop_lock()

    @classmethod
    def write_lock(cls, base_dir: str) -> AsyncContextManager[None]:
        """Async context manager that acquires and releases a write lock."""
        lock_file = cls.get_lock()
        if lock_file:
            path = os.path.join(base_dir, lock_file)
            return FileLock(path).write_lock()
        else:
            return cls._noop_lock()

    @classmethod
    def file_exists(cls, base_dir: str) -> bool:
        """Check if the file exists in the directory.

        Args:
            base_dir: The directory of the file.

        """
        path = os.path.join(base_dir, cls.get_file())
        return os.path.exists(path)

    @classmethod
    def file_open(cls: Type[_RT], base_dir: str) -> _RT:
        """Read a file from the directory, or return :meth:`.get_default` if
        the file does not exist.

        Args:
            base_dir: The directory of the file.

        """
        path = os.path.join(base_dir, cls.get_file())
        try:
            with open(path, 'r') as in_file:
                return cls.open(base_dir, in_file)
        except FileNotFoundError:
            return cls.get_default(base_dir)

    @classmethod
    def file_read(cls: Type[_RT], base_dir: str) -> _RT:
        """Read a file from the directory, or return :meth:`.get_default` if
        the file does not exist.

        Args:
            base_dir: The directory of the file.

        """
        path = os.path.join(base_dir, cls.get_file())
        try:
            with open(path, 'r') as in_file:
                ret = cls.open(base_dir, in_file)
                ret.read(in_file)
                return ret
        except FileNotFoundError:
            return cls.get_default(base_dir)

    @classmethod
    def with_open(cls: Type[_RT], base_dir: str) -> '_FileReadWith[_RT]':
        """Context manager that on entry opens the file, possibly checking
        for the existence of a write lock file first.

        Args:
            base_dir: The directory of the file.

        """
        return _FileReadWith(base_dir, cls, True)

    @classmethod
    def with_read(cls: Type[_RT], base_dir: str) -> '_FileReadWith[_RT]':
        """Context manager that on entry reads the contents of the file,
        possibly checking for the existence of a write lock file first.

        Args:
            base_dir: The directory of the file.

        """
        return _FileReadWith(base_dir, cls, False)


class FileWriteable(FileReadable, metaclass=ABCMeta):
    """Defines an object that can be written to a file. First it is written to
    a temporary file, and then that file is atomically renamed to the final
    filename.

    """

    @abstractmethod
    def get_dir(self) -> str:
        """Return the directory of the file."""
        ...

    @abstractmethod
    def write(self, fp: IO[str]) -> None:
        """Defines how the object is written to a file object.

        Args:
            fp: The text file object open for writing.

        """
        ...

    @classmethod
    def delete(cls, base_dir: str) -> None:
        """Delete the file, if it exists.

        Args:
            base_dir: The directory of the file.

        """
        path = os.path.join(base_dir, cls.get_file())
        try:
            os.unlink(path)
        except OSError:
            pass

    def file_write(self) -> None:
        """Write the file to a temporary filename, and then atomically
        rename the file to its destination filename.

        """
        filename = self.get_file()
        base_dir = self.get_dir()
        path = os.path.join(base_dir, filename)
        with NamedTemporaryFile('w', dir=base_dir, delete=False) as tmp:
            self.write(tmp)
        tmp_path = os.path.join(base_dir, tmp.name)
        os.rename(tmp_path, path)

    @classmethod
    def with_write(cls: Type[_WT], base_dir: str) -> '_FileWriteWith[_WT]':
        """Context manager that on entry creates the lock file and reads the
        contents of the file, and on exit writes the object back to the file
        and removes the lock file.

        Args:
            base_dir: The directory of the file.

        """
        return _FileWriteWith(base_dir, cls)


class _FileReadWith(Generic[_RT]):

    def __init__(self, base_dir: str, cls: Type[_RT], only_open: bool) -> None:
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

    def __init__(self, base_dir: str, cls: Type[_WT]) -> None:
        super().__init__()
        self._base_dir = base_dir
        self._cls = cls
        self._exists = False
        self._lock: Optional[AsyncContextManager[None]] = None
        self._obj: Optional[_WT] = None

    async def _acquire_lock(self) -> None:
        self._lock = self._cls.write_lock(self._base_dir)
        await self._lock.__aenter__()

    async def _release_lock(self) -> None:
        lock = self._lock
        if not lock:
            raise RuntimeError()  # This should not happen.
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
            raise RuntimeError()  # This should not happen.
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
