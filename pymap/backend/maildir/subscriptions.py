
from __future__ import annotations

from collections.abc import Sequence
from typing import TypeVar, IO, Optional

from .io import FileWriteable

__all__ = ['Subscriptions']

_ST = TypeVar('_ST', bound='Subscriptions')


class Subscriptions(FileWriteable):
    """Maintains the set of folders currently subscribed to.

    Args:
        base_dir: The directory of the file.

    """

    def __init__(self, base_dir: str) -> None:
        super().__init__()
        self._base_dir = base_dir
        self._subscribed: dict[str, None] = {}

    @property
    def subscribed(self) -> Sequence[str]:
        """The folders currently subscribed to."""
        return list(self._subscribed.keys())

    def add(self, folder: str) -> None:
        """Add a new folder to the subscriptions."""
        self._subscribed[folder] = None

    def remove(self, folder: str) -> None:
        """Remove a folder from the subscriptions."""
        try:
            del self._subscribed[folder]
        except KeyError:
            pass

    def set(self, folder: str, subscribed: bool) -> None:
        """Set the subscribed status of a folder."""
        if subscribed:
            self.add(folder)
        else:
            self.remove(folder)

    @classmethod
    def get_file(cls) -> str:
        return 'subscriptions'

    @classmethod
    def get_lock(cls) -> Optional[str]:
        return 'subscriptions.lock'

    @classmethod
    def get_default(cls: type[_ST], base_dir: str) -> _ST:
        return cls(base_dir)

    def get_dir(self) -> str:
        return self._base_dir

    @classmethod
    def open(cls: type[_ST], base_dir: str, fp: IO[str]) -> _ST:
        return cls(base_dir)

    def read(self, fp: IO[str]) -> None:
        for line in fp:
            self.add(line.rstrip())

    def write(self, fp: IO[str]) -> None:
        for sub in self._subscribed:
            fp.write(sub + '\r\n')
