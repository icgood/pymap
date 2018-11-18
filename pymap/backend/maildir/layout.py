
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
    def get(cls, path: str, delimiter: str, layout: str) -> 'MaildirLayout':
        """

        Args:
            path: The root path of the inbox.
            delimiter: The nested sub-folder delimiter string.
            layout: The layout name, e.g. ``'++'`` or ``'fs'``.

        Raises:
            ValueError: The layout name was not recognized.

        """
        if layout == '++':
            return DefaultLayout(path, delimiter)
        elif layout == 'fs':
            return FilesystemLayout(path, delimiter)
        else:
            raise ValueError(layout)

    @property
    @abstractmethod
    def path(self) -> str:
        """The root path of the inbox."""
        ...

    @property
    @abstractmethod
    def delimiter(self) -> str:
        """The nested sub-folder delimiter string."""
        ...

    @abstractmethod
    def get_path(self, name: str) -> str:
        """Return the path of the sub-folder.

        Args:
            name: The nested parts of the folder name, not including inbox.

        """
        ...

    @abstractmethod
    def list_folders(self, top: str = 'INBOX') -> Sequence[str]:
        """Return all folders, starting with ``top`` and traversing
        through the sub-folder heirarchy.

        Args:
            top: The top of the folder heirarchy to list.

        Raises:
            FileNotFoundError: The folder did not exist.

        """
        ...

    @abstractmethod
    def get_folder(self, name: str) -> Maildir:
        """Return the existing sub-folder.

        Args:
            name: The delimited sub-folder name, not including inbox.

        Raises:
            FileNotFoundError: The folder did not exist.

        """
        ...

    @abstractmethod
    def add_folder(self, name: str) -> Maildir:
        """Add and return a new sub-folder.

        Args:
            name: The delimited sub-folder name, not including inbox.

        Raises:
            FileExistsError: The folder already exists.
            FileNotFoundError: A parent folder did not exist.

        """
        ...

    @abstractmethod
    def remove_folder(self, name: str) -> None:
        """Remove the existing sub-folder.

        Args:
            name: The delimited sub-folder name, not including inbox.

        Raises:
            FileNotFoundError: The folder did not exist.
            OSError: With :attr:`~errno.ENOTEMPTY`, the folder has sub-folders.

        """
        ...

    @abstractmethod
    def rename_folder(self, source_name: str, dest_name: str) -> Maildir:
        """Rename the existing sub-folder to the destination.

        Args:
            source_name: The delimited source sub-folder name.
            dest_name: The delimited destination sub-folder name.

        Raises:
            FileNotFoundError: The source folder did not exist.
            FileExistsError: The destination folder already exists.

        """
        ...


class _BaseLayout(MaildirLayout, metaclass=ABCMeta):

    def __init__(self, path: str, delimiter: str) -> None:
        super().__init__()
        self._path = path
        self._delimiter = delimiter

    @property
    def path(self) -> str:
        return self._path

    @property
    def delimiter(self) -> str:
        return self._delimiter

    def _split(self, name: str) -> _Parts:
        if name == 'INBOX':
            return []
        return name.split(self._delimiter)

    def _join(self, parts: _Parts) -> str:
        if not parts:
            return 'INBOX'
        return self._delimiter.join(parts)

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

    def get_path(self, name: str) -> str:
        parts = self._split(name)
        return self._get_path(parts)

    def list_folders(self, top: str = 'INBOX') -> Sequence[str]:
        parts = self._split(top)
        return [self._join(sub_parts)
                for sub_parts in self._list_folders(parts)]

    def get_folder(self, name: str) -> Maildir:
        path = self.get_path(name)
        try:
            return Maildir(path, create=False)
        except NoSuchMailboxError:
            raise FileNotFoundError(path)

    def add_folder(self, name: str) -> Maildir:
        parts = self._split(name)
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

    def remove_folder(self, name: str) -> None:
        parts = self._split(name)
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

    def rename_folder(self, source_name: str, dest_name: str) -> Maildir:
        source_parts = self._split(source_name)
        dest_parts = self._split(dest_name)
        for i in range(1, len(dest_parts) - 1):
            parts = dest_parts[0:i]
            path = self._get_path(parts)
            if not os.path.isdir(path):
                name = self._join(parts)
                self.add_folder(name)
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
            elif not subdir or elem.startswith(subdir + self.delimiter):
                elem_path = os.path.join(self._path, elem)
                if os.path.isdir(elem_path):
                    yield self._get_parts(elem)

    def _rename_folder(self, source_parts: _Parts,
                       dest_parts: _Parts) -> Maildir:
        subdir = self._get_subdir(source_parts)
        dest_subdir = self._get_subdir(dest_parts)
        dest_path = self._get_path(dest_parts)
        for elem in os.listdir(self._path):
            if elem == subdir or elem.startswith(subdir + self.delimiter):
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
