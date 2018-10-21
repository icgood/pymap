from functools import total_ordering
from typing import Tuple

from .. import NotParseable, Space, Params, Special
from ..primitives import Atom

__all__ = ['Flag', 'SystemFlag', 'Keyword', 'Seen', 'Recent', 'Deleted',
           'Flagged', 'Answered', 'Draft']


@total_ordering
class Flag(Special[bytes]):
    """Represents a message flag from an IMAP stream.

    Args:
        value: The flag or keyword value.

    """

    def __init__(self, value: bytes) -> None:
        super().__init__()
        self._value = self._capitalize(value)

    @property
    def value(self) -> bytes:
        """The flag or keyword value."""
        return self._value

    @classmethod
    def _capitalize(cls, value: bytes) -> bytes:
        if value.startswith(b'\\'):
            return b'\\' + value[1:].capitalize()
        return value

    def __eq__(self, other) -> bool:
        if isinstance(other, Flag):
            return bytes(self) == bytes(other)
        elif isinstance(other, bytes):
            return bytes(self) == self._capitalize(other)
        return super().__eq__(other)

    def __lt__(self, other) -> bool:
        if isinstance(other, Flag):
            return bytes(self) < bytes(other)
        elif isinstance(other, bytes):
            return bytes(self) < self._capitalize(other)
        return NotImplemented

    def __hash__(self) -> int:
        return hash(bytes(self))

    def __repr__(self) -> str:
        return '<{0} value={1!r}>'.format(self.__class__.__name__, bytes(self))

    def __bytes__(self) -> bytes:
        return self.value

    @classmethod
    def parse(cls, buf: bytes, params: Params) -> Tuple['Flag', bytes]:
        try:
            flag, buf = SystemFlag.parse(buf, params)
        except NotParseable:
            pass
        else:
            return flag, buf
        return Keyword.parse(buf, params)


class SystemFlag(Flag):
    """Base class for system flags defined by the IMAP RFC."""

    @classmethod
    def parse(cls, buf: bytes, params: Params) -> Tuple['Flag', bytes]:
        try:
            _, buf = Space.parse(buf, params)
        except NotParseable:
            pass
        if buf and buf[0] == 0x5c:
            atom, buf = Atom.parse(buf[1:], params)
            return cls(b'\\' + atom.value), buf
        else:
            raise NotParseable(buf)


class Keyword(Flag):
    """Base class for defining custom flag objects. All custom flags, whether
    they are instances or sub-classes, should use this class.

    """

    @classmethod
    def parse(cls, buf: bytes, params: Params) -> Tuple['Keyword', bytes]:
        try:
            _, buf = Space.parse(buf, params)
        except NotParseable:
            pass
        if buf and buf[0] != 0x5c:
            atom, buf = Atom.parse(buf, params)
            return cls(atom.value), buf
        else:
            raise NotParseable(buf)


#: The ``\\Seen`` system flag.
Seen = SystemFlag(br'\Seen')

#: The ``\\Recent`` system flag.
Recent = SystemFlag(br'\Recent')

#: The ``\\Deleted`` system flag.
Deleted = SystemFlag(br'\Deleted')

#: The ``\\Flagged`` system flag.
Flagged = SystemFlag(br'\Flagged')

#: The ``\\Answered`` system flag.
Answered = SystemFlag(br'\Answered')

#: The ``\\Draft`` system flag.
Draft = SystemFlag(br'\Draft')
