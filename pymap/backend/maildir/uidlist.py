
from __future__ import annotations

import random
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import IO, Optional, ClassVar, TypeVar

from pymap.mailbox import MailboxSnapshot

from .io import FileWriteable

__all__ = ['Record', 'UidList']

_UDT = TypeVar('_UDT', bound='UidList')


@dataclass(frozen=True)
class Record:
    """Defines a single record read from the UID list file.

    Args:
        uid: The message UID of the record.
        fields: The metadata fields of the record.
        filename: The filename of the record.

    """

    uid: int
    fields: Mapping[str, str]
    filename: str

    @property
    def key(self) -> str:
        """The :class:`~mailbox.Maildir` key value."""
        return self.filename.split(':', 1)[0]


class UidList(FileWriteable):
    """Maintains the file with UID mapping to maildir files.

    Args:
        base_dir: The directory of the file.
        uid_validity: The UID validity value.
        next_uid: The next assignable message UID value.
        global_uid: The 128-bit global mailbox UID.

    """

    #: The UID list file name, stored in the mailbox directory.
    FILE_NAME: ClassVar[str] = 'dovecot-uidlist'

    #: The UID list lock file, stored adjacent to the UID list file.
    LOCK_FILE: ClassVar[str] = 'dovecot-uidlist.lock'

    def __init__(self, base_dir: str, uid_validity: int,
                 next_uid: int, global_uid: bytes = None) -> None:
        super().__init__()
        self._base_dir = base_dir
        self.uid_validity = uid_validity
        self.next_uid = next_uid
        self.global_uid = global_uid or self._create_guid()
        self._records: dict[int, Record] = {}

    @property
    def records(self) -> Iterable[Record]:
        """The records contained in the UID list file."""
        return self._records.values()

    def get(self, uid: int) -> Record:
        """Get a single record by its UID.

        Args:
            uid: The message UID.

        Raises:
            KeyError: The UID does not exist.

        """
        return self._records[uid]

    def get_all(self, uids: Iterable[int]) -> Mapping[int, Record]:
        """Get records by a set of UIDs.

        Args:
            uids: The message UIDs.

        """
        return {uid: self._records[uid] for uid in uids
                if uid in self._records}

    def set(self, rec: Record) -> None:
        """Add or update the record in the UID list file."""
        self._records[rec.uid] = rec

    def remove(self, uid: int) -> None:
        """Remove the record from the UID list file.

        Raises:
            KeyError: The UID does not exist.

        """
        del self._records[uid]

    @classmethod
    def _build_line(cls, rec: Record) -> str:
        parts = ['%d' % rec.uid]
        for key, val in sorted(rec.fields.items()):
            if val is not None:
                parts.append(' ')
                parts.append(key[0:1])
                parts.append(val)
        parts.append(' :')
        parts.append(rec.filename)
        parts.append('\r\n')
        return ''.join(parts)

    @classmethod
    def _read_line(cls, line: str) -> Record:
        before, filename = line.split(':', 1)
        fields: dict[str, str] = {}
        data = before.split(' ')
        num = int(data[0])
        for col in data[1:]:
            if col:
                fields[col[0]] = col[1:]
        return Record(num, fields, filename.rstrip())

    @classmethod
    def _read_header(cls: type[_UDT], base_dir: str, line: str) -> _UDT:
        data = line.split()
        if data[0] != '3':
            raise ValueError(line)
        uid_validity: Optional[int] = None
        next_uid: Optional[int] = None
        global_uid: Optional[bytes] = None
        for field in data[1:]:
            if field[0] == 'V':
                uid_validity = int(field[1:])
            elif field[0] == 'N':
                next_uid = int(field[1:])
            elif field[0] == 'G':
                global_uid = field[1:].encode('ascii')
        if uid_validity is None or next_uid is None or global_uid is None:
            raise ValueError(line)
        return cls(base_dir, uid_validity, next_uid, global_uid)

    @classmethod
    def _create_guid(cls) -> bytes:
        return b'%032x' % random.getrandbits(128)

    def _build_header(self) -> str:
        global_uid = self.global_uid.decode('ascii')
        return ''.join(['3 V', str(self.uid_validity),
                        ' N', str(self.next_uid),
                        ' G', global_uid, '\r\n'])

    @classmethod
    def get_file(cls) -> str:
        return cls.FILE_NAME

    @classmethod
    def get_lock(cls) -> str:
        return cls.LOCK_FILE

    def get_dir(self) -> str:
        return self._base_dir

    @classmethod
    def get_default(cls: type[_UDT], base_dir: str) -> _UDT:
        return cls(base_dir, MailboxSnapshot.new_uid_validity(), 1)

    def write(self, fp: IO[str]) -> None:
        fp.write(self._build_header())
        for rec in self.records:
            fp.write(self._build_line(rec))

    @classmethod
    def open(cls: type[_UDT], base_dir: str, fp: IO[str]) -> _UDT:
        header = fp.readline()
        ret = cls._read_header(base_dir, header)
        return ret

    def read(self, fp: IO[str]) -> None:
        for line in fp:
            self.set(self._read_line(line))
