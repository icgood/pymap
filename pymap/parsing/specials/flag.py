
from __future__ import annotations

from functools import total_ordering
from typing import Union

from .. import Params, Parseable, Space
from ..exceptions import NotParseable
from ..primitives import Atom

__all__ = ['Flag', 'get_system_flags', 'Seen', 'Recent', 'Deleted', 'Flagged',
           'Answered', 'Draft', 'Wildcard']


@total_ordering
class Flag(Parseable[bytes]):
    """Represents a message flag from an IMAP stream.

    Args:
        value: The flag or keyword value.

    """

    def __init__(self, value: Union[str, bytes]) -> None:
        super().__init__()
        if isinstance(value, bytes):
            value_bytes = value
        else:
            value_bytes = bytes(value, 'ascii')
        self._value = self._capitalize(value_bytes)
        self._hash = hash(self._value)

    @property
    def value(self) -> bytes:
        """The flag or keyword value."""
        return self._value

    @property
    def is_system(self) -> bool:
        """True if the flag is an RFC-defined IMAP system flag."""
        return self.value.startswith(b'\\')

    @classmethod
    def _capitalize(cls, value: bytes) -> bytes:
        if value.startswith(b'\\'):
            return b'\\' + value[1:].capitalize()
        return value

    def __eq__(self, other) -> bool:
        if isinstance(other, Flag):
            return self._value == other._value
        elif isinstance(other, bytes):
            return self._value == self._capitalize(other)
        return super().__eq__(other)

    def __lt__(self, other) -> bool:
        if isinstance(other, Flag):
            other_bytes = bytes(other)
        elif isinstance(other, bytes):
            other_bytes = self._capitalize(other)
        else:
            return NotImplemented
        if self.is_system and not other_bytes.startswith(b'\\'):
            return True
        elif not self.is_system and other_bytes.startswith(b'\\'):
            return False
        return bytes(self) < other_bytes

    def __hash__(self) -> int:
        return self._hash

    def __repr__(self) -> str:
        return '<{0} value={1!r}>'.format(type(self).__name__, bytes(self))

    def __bytes__(self) -> bytes:
        return self.value

    def __str__(self) -> str:
        return self.value.decode('ascii')

    @classmethod
    def parse(cls, buf: memoryview, params: Params) \
            -> tuple[Flag, memoryview]:
        try:
            _, buf = Space.parse(buf, params)
        except NotParseable:
            pass
        if buf:
            if buf[0] == 0x5c:
                atom, buf = Atom.parse(buf[1:], params)
                return cls(b'\\' + atom.value), buf
            else:
                atom, buf = Atom.parse(buf, params)
                return cls(atom.value), buf
        raise NotParseable(buf)


def get_system_flags() -> frozenset[Flag]:
    """Return the set of implemented system flags."""
    return frozenset({Seen, Recent, Deleted, Flagged, Answered, Draft})


#: The ``\\Seen`` system flag.
Seen = Flag(br'\Seen')

#: The ``\\Recent`` system flag.
Recent = Flag(br'\Recent')

#: The ``\\Deleted`` system flag.
Deleted = Flag(br'\Deleted')

#: The ``\\Flagged`` system flag.
Flagged = Flag(br'\Flagged')

#: The ``\\Answered`` system flag.
Answered = Flag(br'\Answered')

#: The ``\\Draft`` system flag.
Draft = Flag(br'\Draft')

#: The ``\\*`` special wildcard flag.
Wildcard = Flag(br'\*')
