
import errno
import os
import os.path
from abc import abstractmethod, ABCMeta
from mailbox import Maildir, NoSuchMailboxError  # type: ignore
from typing import Sequence, Iterable
from typing_extensions import Protocol

__all__ = ['MaildirLayout', 'DefaultLayout', 'FilesystemLayout']

_Parts = Sequence[str]


class MaildirLayout(Protocol):
    """Manages the folder layout of a :class:`~mailbox.Maildir` inbox.

    See Also:
        `Directory Structure
        <https://wiki.dovecot.org/MailboxFormat/Maildir#line-130>`_

    """

    @classmethod
    def get(cls, path: str, layout: str) -> 'MaildirLayout':
        """

        Args:
            path: The root path of the inbox.
            layout: The layout name, e.g. ``'++'`` or ``'fs'``.

        Raises:
            ValueError: The layout name was not recognized.

        """
        if layout == '++':
            return DefaultLayout(path)
        elif layout == 'fs':
            return FilesystemLayout(path)
        else:
            raise ValueError(layout)

    @property
    @abstractmethod
    def path(self) -> str:
        """The root path of the inbox."""
        ...

    @abstractmethod
    def get_path(self, name: str, delimiter: str) -> str:
        """Return the path of the sub-folder.

        Args:
            name: The nested parts of the folder name, not including inbox.
            delimiter: The nested sub-folder delimiter string.

        """
        ...

    @abstractmethod
    def list_folders(self, delimiter: str, top: str = 'INBOX') \
            -> Sequence[str]:
        """Return all folders, starting with ``top`` and traversing
        through the sub-folder heirarchy.

        Args:
            delimiter: The nested sub-folder delimiter string.
            top: The top of the folder heirarchy to list.

        Raises:
            FileNotFoundError: The folder did not exist.

        """
        ...

    @abstractmethod
    def get_folder(self, name: str, delimiter: str) -> Maildir:
        """Return the existing sub-folder.

        Args:
            name: The delimited sub-folder name, not including inbox.
            delimiter: The nested sub-folder delimiter string.

        Raises:
            FileNotFoundError: The folder did not exist.

        """
        ...

    @abstractmethod
    def add_folder(self, name: str, delimiter: str) -> Maildir:
        """Add and return a new sub-folder.

        Args:
            name: The delimited sub-folder name, not including inbox.
            delimiter: The nested sub-folder delimiter string.

        Raises:
            FileExistsError: The folder already exists.
            FileNotFoundError: A parent folder did not exist.

        """
        ...

    @abstractmethod
    def remove_folder(self, name: str, delimiter: str) -> None:
        """Remove the existing sub-folder.

        Args:
            name: The delimited sub-folder name, not including inbox.
            delimiter: The nested sub-folder delimiter string.

        Raises:
            FileNotFoundError: The folder did not exist.
            OSError: With :attr:`~errno.ENOTEMPTY`, the folder has sub-folders.

        """
        ...

    @abstractmethod
    def rename_folder(self, source_name: str, dest_name: str,
                      delimiter: str) -> Maildir:
        """Rename the existing sub-folder to the destination.

        Args:
            source_name: The delimited source sub-folder name.
            dest_name: The delimited destination sub-folder name.
            delimiter: The nested sub-folder delimiter string.

        Raises:
            FileNotFoundError: The source folder did not exist.
            FileExistsError: The destination folder already exists.

        """
        ...


class _BaseLayout(MaildirLayout, metaclass=ABCMeta):

    def __init__(self, path: str) -> None:
        super().__init__()
        self._path = path

    @property
    def path(self) -> str:
        return self._path

    @classmethod
    def _split(cls, name: str, delimiter: str) -> _Parts:
        if name == 'INBOX':
            return []
        return name.split(delimiter)

    @classmethod
    def _join(cls, parts: _Parts, delimiter: str) -> str:
        if not parts:
            return 'INBOX'
        return delimiter.join(parts)

    def _can_remove(self, parts: _Parts) -> bool:
        return True

    @abstractmethod
    def _get_path(self, parts: _Parts) -> str:
        ...

    @abstractmethod
    def _list_folders(self, parts: _Parts) -> Iterable[_Parts]:
        ...

    @abstractmethod
    def _rename_folder(self, source_parts: _Parts,
                       dest_parts: _Parts) -> Maildir:
        ...

    def get_path(self, name: str, delimiter: str) -> str:
        parts = self._split(name, delimiter)
        return self._get_path(parts)

    def list_folders(self, delimiter: str, top: str = 'INBOX') \
            -> Sequence[str]:
        parts = self._split(top, delimiter)
        return [self._join(sub_parts, delimiter)
                for sub_parts in self._list_folders(parts)]

    def get_folder(self, name: str, delimiter: str) -> Maildir:
        path = self.get_path(name, delimiter)
        try:
            return Maildir(path, create=False)
        except NoSuchMailboxError:
            raise FileNotFoundError(path)

    def add_folder(self, name: str, delimiter: str) -> Maildir:
        parts = self._split(name, delimiter)
        for i in range(1, len(parts) - 1):
            path = self._get_path(parts[0:i])
            if not os.path.isdir(path):
                raise FileNotFoundError(path)
        path = self._get_path(parts)
        maildir = Maildir(path, create=True)
        maildirfolder = os.path.join(path, 'maildirfolder')
        with open(maildirfolder, 'x'):
            pass
        return maildir

    def remove_folder(self, name: str, delimiter: str) -> None:
        parts = self._split(name, delimiter)
        path = self._get_path(parts)
        if not self._can_remove(parts):
            path = self._get_path(parts)
            raise OSError(errno.ENOTEMPTY, 'Directory not empty: '
                          + repr(path))
        for root, dirs, files in os.walk(path, topdown=False):
            for entry in files:
                os.remove(os.path.join(root, entry))
            for entry in dirs:
                os.rmdir(os.path.join(root, entry))
        os.rmdir(path)

    def rename_folder(self, source_name: str, dest_name: str,
                      delimiter: str) -> Maildir:
        source_parts = self._split(source_name, delimiter)
        dest_parts = self._split(dest_name, delimiter)
        for i in range(1, len(dest_parts) - 1):
            parts = dest_parts[0:i]
            path = self._get_path(parts)
            if not os.path.isdir(path):
                name = self._join(parts, delimiter)
                self.add_folder(name, delimiter)
        return self._rename_folder(source_parts, dest_parts)


class DefaultLayout(_BaseLayout):
    """The default Maildir++ layout, which uses sub-folder names starting
    with a ``.`` and nested using a delimiter, e.g.::

        .Trash/
        .Important.To-Do/
        .Important.Misc/

    """

    def _get_path(self, parts: _Parts) -> str:
        return os.path.join(self._path, self._get_subdir(parts))

    @classmethod
    def _get_subdir(cls, parts: _Parts) -> str:
        if not parts:
            return ''
        return '.' + '.'.join(parts)

    @classmethod
    def _get_parts(cls, subdir: str) -> _Parts:
        if not subdir:
            return []
        return subdir[1:].split('.')

    def _list_folders(self, parts: _Parts) -> Iterable[_Parts]:
        subdir = self._get_subdir(parts)
        path = self._get_path(parts)
        if not os.path.isdir(path):
            return
        yield parts
        for elem in os.listdir(self._path):
            if elem in ('new', 'cur', 'tmp'):
                pass
            elif not subdir or elem.startswith(subdir + '.'):
                elem_path = os.path.join(self._path, elem)
                if os.path.isdir(elem_path):
                    yield self._get_parts(elem)

    def _rename_folder(self, source_parts: _Parts,
                       dest_parts: _Parts) -> Maildir:
        subdir = self._get_subdir(source_parts)
        dest_subdir = self._get_subdir(dest_parts)
        dest_path = self._get_path(dest_parts)
        for elem in os.listdir(self._path):
            if elem == subdir or elem.startswith(subdir + '.'):
                elem_path = os.path.join(self._path, elem)
                if os.path.isdir(elem_path):
                    dest_elem = dest_subdir + elem[len(subdir):]
                    dest_elem_path = os.path.join(self._path, dest_elem)
                    os.rename(elem_path, dest_elem_path)
        return Maildir(dest_path, create=False)


class FilesystemLayout(_BaseLayout):
    """The ``fs`` layout, which uses nested sub-directories on the filesystem,
    e.g.::

        Trash/
        Important/To-Do/
        Important/Misc/

    """

    def _get_path(self, parts: _Parts) -> str:
        return os.path.join(self._path, *parts)

    def _can_remove(self, parts: _Parts) -> bool:
        path = self._get_path(parts)
        for elem in os.listdir(path):
            if elem not in ('new', 'cur', 'tmp'):
                elem_path = os.path.join(path, elem)
                if os.path.isdir(elem_path):
                    return False
        return True

    def _list_folders(self, parts: _Parts) -> Iterable[_Parts]:
        path = self._get_path(parts)
        if not os.path.isdir(path):
            return
        yield parts
        for elem in os.listdir(path):
            if elem not in ('new', 'cur', 'tmp'):
                for sub_parts in self._list_folders(list(parts) + [elem]):
                    yield sub_parts

    def _rename_folder(self, source_parts: _Parts,
                       dest_parts: _Parts) -> Maildir:
        path = self._get_path(source_parts)
        dest_path = self._get_path(dest_parts)
        os.rename(path, dest_path)
        return Maildir(dest_path, create=False)
