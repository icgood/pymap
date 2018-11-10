
import hashlib
import struct
from collections import OrderedDict
from typing import IO, Any, Optional, Iterable, Mapping, Dict, \
    NamedTuple, TypeVar, Type

from pymap.mailbox import BaseMailbox

from .io import FileWriteable

__all__ = ['Record', 'UidList']

_UDT = TypeVar('_UDT', bound='UidList')


class Record(NamedTuple):
    uid: int
    fields: Mapping[str, Any]
    filename: str


class UidList(FileWriteable):
    """Maintains the file with UID mapping to maildir files.

    Args:
        base_dir: The directory of the file.
        uid_validity: The UID validity value.
        next_uid: The next assignable message UID value.
        global_uid: The 128-bit global mailbox UID.

    """

    def __init__(self, base_dir: str, uid_validity: int,
                 next_uid: int, global_uid: bytes = None) -> None:
        super().__init__()
        self._base_dir = base_dir
        self.uid_validity = uid_validity
        self.next_uid = next_uid
        self.global_uid = global_uid or self._create_guid(base_dir)
        self._records: Dict[int, Record] = OrderedDict()

    @property
    def records(self) -> Iterable[Record]:
        """The records contained in the UID list file."""
        return self._records.values()

    def get(self, uid: int) -> Record:
        """Get a single record by its UID.

        Raises:
            KeyError: The UID does not exist.

        """
        return self._records[uid]

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
            parts.append(' ')
            parts.append(key[0:1])
            parts.append(str(val))
        parts.append(' :')
        parts.append(rec.filename)
        parts.append('\r\n')
        return ''.join(parts)

    @classmethod
    def _read_line(cls, line: str) -> Record:
        before, filename = line.split(':', 1)
        fields: Dict[str, str] = {}
        data = before.split(' ')
        num = int(data[0])
        for col in data[1:]:
            if col:
                fields[col[0]] = col[1:]
        return Record(num, fields, filename.rstrip())

    @classmethod
    def _read_guid_hex(cls, field: str) -> bytes:
        split = int(len(field) / 2)
        left, right = int(field[0:split], 16), int(field[split:], 16)
        return struct.pack('=QQ', left, right)

    @classmethod
    def _read_header(cls: Type[_UDT], base_dir: str, line: str) -> _UDT:
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
                global_uid = cls._read_guid_hex(field[1:])
        if uid_validity is None or next_uid is None or global_uid is None:
            raise ValueError(line)
        return cls(base_dir, uid_validity, next_uid, global_uid)

    def _create_guid(self, base_dir: str) -> bytes:
        ret = hashlib.sha256()
        ret.update(base_dir.encode('utf-8', 'replace'))
        ret.update(struct.pack('=L', self.uid_validity))
        return ret.digest()[0:16]

    def _get_guid_hex(self) -> str:
        left, right = struct.unpack('=QQ', self.global_uid)
        return format(left, 'x') + format(right, 'x')

    def _build_header(self) -> str:
        return ''.join(['3 V', str(self.uid_validity),
                        ' N', str(self.next_uid),
                        ' G', self._get_guid_hex(), '\r\n'])

    @classmethod
    def get_file(cls) -> str:
        return 'dovecot-uidlist'

    @classmethod
    def get_lock(cls) -> str:
        return 'dovecot-uidlist.lock'

    def get_dir(self) -> str:
        return self._base_dir

    @classmethod
    def get_default(cls: Type[_UDT], base_dir: str) -> _UDT:
        return cls(base_dir, BaseMailbox.new_uid_validity(), 1)

    def write(self, fp: IO[str]) -> None:
        fp.write(self._build_header())
        for rec in self.records:
            fp.write(self._build_line(rec))

    @classmethod
    def open(cls: Type[_UDT], base_dir: str, fp: IO[str]) -> _UDT:
        header = fp.readline()
        ret = cls._read_header(base_dir, header)
        return ret

    def read(self, fp: IO[str]) -> None:
        for line in fp:
            self.set(self._read_line(line))
