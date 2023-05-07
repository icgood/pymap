
from __future__ import annotations

import os.path
from collections.abc import Sequence
from typing import IO, Self

from .io import FileWriteable

__all__ = ['Subscriptions']


class Subscriptions(FileWriteable):
    """Maintains the set of folders currently subscribed to.

    Args:
        path: The directory of the file.

    """

    def __init__(self, path: str) -> None:
        super().__init__(path)
        self._subscribed: dict[str, None] = {}

    @property
    def empty(self) -> bool:
        return not self._subscribed

    @property
    def subscribed(self) -> Sequence[str]:
        """The folders currently subscribed to."""
        return list(self._subscribed.keys())

    def add(self, folder: str) -> None:
        """Add a new folder to the subscriptions."""
        self._subscribed[folder] = None
        self.touch()

    def remove(self, folder: str) -> None:
        """Remove a folder from the subscriptions."""
        self._subscribed.pop(folder, None)
        self.touch()

    def set(self, folder: str, subscribed: bool) -> None:
        """Set the subscribed status of a folder."""
        if subscribed:
            self.add(folder)
        else:
            self.remove(folder)

    @classmethod
    def get_file(cls, path: str) -> str:
        return os.path.join(path, 'subscriptions')

    @classmethod
    def get_lock(cls, path: str) -> str | None:
        return os.path.join(path, 'subscriptions.lock')

    @classmethod
    def get_default(cls, path: str) -> Self:
        return cls(path)

    @classmethod
    def open(cls, path: str, fp: IO[str]) -> Self:
        return cls(path)

    def read(self, fp: IO[str]) -> None:
        for line in fp:
            self.add(line.rstrip())

    def write(self, fp: IO[str]) -> None:
        for sub in self._subscribed:
            fp.write(sub + '\r\n')
