"""Primitive parseable objects in the IMAP protocol."""

from __future__ import annotations

import re
from abc import abstractmethod, ABCMeta
from collections.abc import Iterable, Iterator, Sequence
from functools import total_ordering
from re import Match
from typing import cast, Union, Optional, SupportsBytes

from . import Parseable, ExpectedParseable, Params
from .exceptions import NotParseable
from .state import ExpectContinuation
from ..bytes import rev, MaybeBytes, MaybeBytesT, BytesFormat, WriteStream, \
    Writeable

__all__ = ['Nil', 'Number', 'Atom', 'List', 'String',
           'QuotedString', 'LiteralString']


class Nil(Parseable[None]):
    """Represents a ``NIL`` object from an IMAP stream."""

    _nil_pattern = rev.compile(b'^NIL$', re.I)

    __slots__: list[str] = []

    def __init__(self) -> None:
        super().__init__()

    @property
    def value(self) -> None:
        """Always returns ``None``."""
        return None

    def __bytes__(self) -> bytes:
        return b'NIL'

    def __hash__(self) -> int:
        return hash(Nil)

    def __eq__(self, other) -> bool:
        if isinstance(other, Nil):
            return True
        return super().__eq__(other)

    @classmethod
    def parse(cls, buf: memoryview, params: Params) \
            -> tuple[Nil, memoryview]:
        start = cls._whitespace_length(buf)
        match = cls._atom_pattern.match(buf, start)
        if not match:
            raise NotParseable(buf)
        atom = match.group(0)
        if not cls._nil_pattern.match(atom):
            raise NotParseable(buf)
        return cls(), buf[match.end(0):]


@total_ordering
class Number(Parseable[int]):
    """Represents a number object from an IMAP stream.

    Args:
        num: The integer value.

    """

    _num_pattern = rev.compile(br'^\d+$')

    __slots__ = ['num', '_raw']

    def __init__(self, num: int) -> None:
        super().__init__()
        self.num = num
        self._raw = b'%d' % num

    @property
    def value(self) -> int:
        """The integer value."""
        return self.num

    @classmethod
    def parse(cls, buf: memoryview, params: Params) \
            -> tuple[Number, memoryview]:
        start = cls._whitespace_length(buf)
        match = cls._atom_pattern.match(buf, start)
        if not match:
            raise NotParseable(buf)
        atom = match.group(0)
        if not cls._num_pattern.match(atom):
            raise NotParseable(buf)
        return cls(int(match.group(0))), buf[match.end(0):]

    def __bytes__(self) -> bytes:
        return self._raw

    def __hash__(self) -> int:
        return hash((Number, self.value))

    def __eq__(self, other) -> bool:
        if isinstance(other, Number):
            return self.value == other.value
        elif isinstance(other, int):
            return self.value == other
        return super().__eq__(other)

    def __lt__(self, other) -> bool:
        if isinstance(other, Number):
            return self.value < other.value
        elif isinstance(other, int):
            return self.value < other
        return NotImplemented


class Atom(Parseable[bytes]):
    """Represents an atom object from an IMAP stream.

    Args:
        value: The atom bytestring.

    """

    __slots__ = ['_value']

    def __init__(self, value: bytes) -> None:
        super().__init__()
        self._value = value

    @property
    def value(self) -> bytes:
        """The atom bytestring."""
        return self._value

    @classmethod
    def parse(cls, buf: memoryview, params: Params) \
            -> tuple[Atom, memoryview]:
        start = cls._whitespace_length(buf)
        match = cls._atom_pattern.match(buf, start)
        if not match:
            raise NotParseable(buf[start:])
        atom = match.group(0)
        return cls(atom), buf[match.end(0):]

    def __bytes__(self) -> bytes:
        return self.value

    def __hash__(self) -> int:
        return hash((Atom, self.value))

    def __eq__(self, other) -> bool:
        if isinstance(other, Atom):
            return self.value == other.value
        return super().__eq__(other)


class String(Parseable[bytes], metaclass=ABCMeta):
    """Represents a string object from an IMAP string. This object may not be
    instantiated directly, use one of its derivatives instead.

    """

    _MAX_LEN = 4096

    __slots__: list[str] = []

    @property
    @abstractmethod
    def binary(self) -> bool:
        """True if the string should be transmitted as binary."""
        ...

    @property
    @abstractmethod
    def length(self) -> int:
        """The length of the string value."""
        ...

    @classmethod
    def parse(cls, buf: memoryview, params: Params) \
            -> tuple[String, memoryview]:
        try:
            return QuotedString.parse(buf, params)
        except NotParseable:
            pass
        return LiteralString.parse(buf, params)

    @classmethod
    def build(cls, value: object, binary: bool = False,
              fallback: object = None) -> Union[Nil, String]:
        """Produce either a :class:`QuotedString` or :class:`LiteralString`
        based on the contents of ``data``. This is useful to improve
        readability of response data.

        Args:
            value: The string to serialize.
            binary: True if the string should be transmitted as binary.
            fallback: The default value to use if ``value`` is None.

        """
        if value is None:
            if fallback is None:
                return Nil()
            else:
                return cls.build(fallback, binary)
        elif not value:
            return QuotedString(b'')
        elif isinstance(value, bytes):
            ascii_ = value
        elif isinstance(value, memoryview):
            ascii_ = bytes(value)
        elif hasattr(value, '__bytes__'):
            ascii_ = bytes(cast(SupportsBytes, value))
        elif isinstance(value, str) or hasattr(value, '__str__'):
            value = str(value)
            try:
                ascii_ = bytes(value, 'ascii')
            except UnicodeEncodeError:
                ascii_ = bytes(value, 'utf-8', 'replace')
                return LiteralString(ascii_, binary)
        else:
            raise TypeError(value)
        if not binary and len(ascii_) < 64 \
                and b'\n' not in ascii_ \
                and b'\x00' not in ascii_:
            return QuotedString(ascii_)
        else:
            return LiteralString(ascii_, binary)

    def __bytes__(self) -> bytes:
        raise NotImplementedError

    def __hash__(self) -> int:
        return hash((String, self.value))

    def __eq__(self, other) -> bool:
        if isinstance(other, String):
            return self.value == other.value
        return super().__eq__(other)


class QuotedString(String):
    """Represents a string object from an IMAP stream that was encased in
    double-quotes.

    Args:
        string: The string value.

    """

    _quoted_pattern = rev.compile(br'(?:\r|\n|\\.|\")')
    _quoted_specials_pattern = rev.compile(br'[\"\\]')

    __slots__ = ['_string', '_raw']

    def __init__(self, string: bytes, raw: bytes = None) -> None:
        super().__init__()
        self._string = string
        self._raw = raw

    @property
    def value(self) -> bytes:
        """The string value."""
        return self._string

    @property
    def binary(self) -> bool:
        return False

    @property
    def length(self) -> int:
        return len(self._string)

    @classmethod
    def parse(cls, buf: memoryview, params: Params) \
            -> tuple[QuotedString, memoryview]:
        start = cls._whitespace_length(buf)
        if buf[start:start + 1] != b'"':
            raise NotParseable(buf)
        marker = start + 1
        unquoted = bytearray()
        for match in cls._quoted_pattern.finditer(buf, marker):
            unquoted += buf[marker:match.start(0)]
            match_group = match.group(0)
            if match_group in (b'\r', b'\n'):
                raise NotParseable(buf)
            elif match_group.startswith(b'\\'):
                escape_char = match_group[-1:]
                if escape_char in (b'\\', b'"'):
                    unquoted += escape_char
                else:
                    raise NotParseable(buf)
                marker = match.end(0)
            else:
                end = match.end(0)
                quoted = buf[start:end + 1]
                return cls(bytes(unquoted), bytes(quoted)), buf[end:]
        raise NotParseable(buf)

    @classmethod
    def _escape_quoted_specials(cls, match: Match) -> bytes:
        return b'\\' + match.group(0)

    def __bytes__(self) -> bytes:
        if self._raw is not None:
            return bytes(self._raw)
        pat = self._quoted_specials_pattern
        quoted_string = pat.sub(self._escape_quoted_specials, self.value)
        self._raw = BytesFormat(b'"%b"') % (quoted_string, )
        return self._raw


class LiteralString(String):
    """Represents a string object from an IMAP stream that used the literal
    syntax.

    Args:
        string: The literal string value.
        binary: True if the string is considered binary data.

    """

    _literal_pattern = rev.compile(br'(~?){(\d+)(\+?)}\r?\n')

    __slots__ = ['_string', '_length', '_binary', '_raw']

    def __init__(self, string: Union[bytes, Writeable],
                 binary: bool = False) -> None:
        super().__init__()
        self._string = string
        self._length = len(string)
        self._binary = binary
        self._raw: Optional[bytes] = None

    @property
    def value(self) -> bytes:
        return bytes(self._string)

    @property
    def binary(self) -> bool:
        return self._binary

    @property
    def length(self) -> int:
        return self._length

    @property
    def _prefix(self) -> bytes:
        binary_prefix = b'~' if self.binary else b''
        return b'%b{%d}\r\n' % (binary_prefix, self.length)

    @classmethod
    def _check_too_big(cls, params: Params, length: int) -> bool:
        if params.command_name == b'APPEND':
            max_len = params.max_append_len
        else:
            max_len = cls._MAX_LEN
        return max_len is not None and length > max_len

    @classmethod
    def parse(cls, buf: memoryview, params: Params) \
            -> tuple[LiteralString, memoryview]:
        start = cls._whitespace_length(buf)
        match = cls._literal_pattern.match(buf, start)
        if not match:
            raise NotParseable(buf)
        binary = match.group(1) == b'~'
        literal_length = int(match.group(2))
        if cls._check_too_big(params, literal_length):
            raise NotParseable(buf, b'TOOBIG')
        elif match.group(3) == b'+':
            buf = buf[match.end(0):]
            literal = bytes(buf[0:literal_length])
        elif len(buf) > match.end(0):
            raise NotParseable(buf[match.end(0):])
        elif params.allow_continuations:
            expected = ExpectContinuation(b'Literal string', literal_length)
            buf = expected.expect(params.state)
            literal = bytes(buf[0:literal_length])
        else:
            raise NotParseable(buf)
        if len(literal) != literal_length:
            raise NotParseable(buf)
        return cls(literal, binary), buf[literal_length:]

    def write(self, writer: WriteStream) -> None:
        writer.write(self._prefix)
        if isinstance(self._string, Writeable):
            self._string.write(writer)
        else:
            writer.write(self._string)

    def __len__(self) -> int:
        return len(self._prefix) + self.length

    def __bytes__(self) -> bytes:
        if self._raw is None:
            self._raw = self.tobytes()
        return self._raw


class List(Parseable[Sequence[MaybeBytes]]):
    """Represents a list of :class:`Parseable` objects from an IMAP stream.

    Args:
        items: The list of parsed objects.
        sort: If True, the list of items is sorted.

    """

    _end_pattern = rev.compile(br' *\)')

    __slots__ = ['items']

    def __init__(self, items: Iterable[MaybeBytes],
                 sort: bool = False) -> None:
        super().__init__()
        if sort:
            items_list = sorted(items)  # type: ignore
        else:
            items_list = list(items)
        self.items: Sequence[MaybeBytes] = items_list

    @property
    def value(self) -> Sequence[MaybeBytes]:
        """The list of parsed objects."""
        return self.items

    def get_as(self, cls: type[MaybeBytesT]) -> Sequence[MaybeBytesT]:
        """Return the list of parsed objects."""
        _ = cls  # noqa
        return cast(Sequence[MaybeBytesT], self.items)

    def __iter__(self) -> Iterator[MaybeBytes]:
        return iter(self.value)

    def __len__(self) -> int:
        return len(self.value)

    @classmethod
    def parse(cls, buf: memoryview, params: Params) \
            -> tuple[List, memoryview]:
        start = cls._whitespace_length(buf)
        if buf[start:start + 1] != b'(':
            raise NotParseable(buf)
        items: list[Parseable] = []
        buf = buf[start + 1:]
        while True:
            match = cls._end_pattern.match(buf)
            if match:
                return cls(items), buf[match.end(0):]
            elif items and not cls._whitespace_length(buf):
                raise NotParseable(buf)
            params_copy = params.copy(expected=params.list_expected)
            item, buf = ExpectedParseable.parse(buf, params_copy)
            items.append(item)

    def write(self, writer: WriteStream) -> None:
        writer.write(b'(')
        is_first = True
        for i, item in enumerate(self.items):
            if is_first:
                is_first = False
            else:
                writer.write(b' ')
            if isinstance(item, Writeable):
                item.write(writer)
            else:
                writer.write(bytes(item))
        writer.write(b')')

    def __bytes__(self) -> bytes:
        raw_items = BytesFormat(b' ').join(self.items)
        return b'(%b)' % raw_items

    def __hash__(self) -> int:
        return hash((List, self.value))

    def __eq__(self, other) -> bool:
        if isinstance(other, List):
            return self.__eq__(other.value)
        elif isinstance(other, Sequence):
            if len(self.value) != len(other):
                return False
            for i, val in enumerate(self.value):
                if val != other[i]:
                    return False
            return True
        return super().__eq__(other)
