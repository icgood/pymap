# Copyright (c) 2018 Ian C. Good
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#

import re
from collections.abc import Sequence as SequenceABC
from functools import total_ordering
from typing import Tuple, List, Union, Iterable, Any, Sequence

from . import Parseable, NotParseable, RequiresContinuation, Primitive, Params
from .typing import ParseableListType

__all__ = ['Nil', 'Number', 'Atom', 'ListP', 'String',
           'QuotedString', 'LiteralString']


class Nil(Primitive[None]):
    """Represents a NIL object from an IMAP stream."""

    _nil_pattern = re.compile(b'^NIL$', re.I)

    @classmethod
    def parse(cls, buf: bytes, params: Params) -> Tuple['Nil', bytes]:
        start = cls._whitespace_length(buf)
        match = cls._atom_pattern.match(buf, start)
        if not match:
            raise NotParseable(buf)
        atom = match.group(0)
        if not cls._nil_pattern.match(atom):
            raise NotParseable(buf)
        return cls(), buf[match.end(0):]

    def __bytes__(self):
        return b'NIL'

    def __hash__(self):
        return hash(Nil)

    def __eq__(self, other):
        if isinstance(other, Nil):
            return True
        return NotImplemented


@total_ordering
class Number(Primitive[int]):
    """Represents a number object from an IMAP stream."""

    _num_pattern = re.compile(br'^\d+$')

    def __init__(self, num: int) -> None:
        super().__init__()
        self.value = num
        self._raw = bytes(str(self.value), 'ascii')

    @classmethod
    def parse(cls, buf: bytes, params: Params) -> Tuple['Number', bytes]:
        start = cls._whitespace_length(buf)
        match = cls._atom_pattern.match(buf, start)
        if not match:
            raise NotParseable(buf)
        atom = match.group(0)
        if not cls._num_pattern.match(atom):
            raise NotParseable(buf)
        return cls(int(match.group(0))), buf[match.end(0):]

    def __bytes__(self):
        return self._raw

    def __hash__(self):
        return hash((Number, self.value))

    def __eq__(self, other):
        if isinstance(other, Number):
            return self.value == other.value
        elif isinstance(other, int):
            return self.value == other
        return NotImplemented

    def __lt__(self, other):
        if isinstance(other, Number):
            return self.value < other.value
        elif isinstance(other, int):
            return self.value < other
        return NotImplemented


class Atom(Primitive[bytes]):
    """Represents an atom object from an IMAP stream."""

    def __init__(self, value: bytes) -> None:
        super().__init__()
        self.value = value

    @classmethod
    def parse(cls, buf: bytes, params: Params) -> Tuple['Atom', bytes]:
        start = cls._whitespace_length(buf)
        match = cls._atom_pattern.match(buf, start)
        if not match:
            raise NotParseable(buf[start:])
        atom = match.group(0)
        return cls(atom), buf[match.end(0):]

    def __bytes__(self):
        return bytes(self.value)

    def __hash__(self):
        return hash((Atom, self.value))

    def __eq__(self, other):
        if isinstance(other, Atom):
            return self.value == other.value
        return NotImplemented


class String(Primitive[bytes]):
    """Represents a string object from an IMAP string. This object may not be
    instantiated directly, use one of its derivatives instead.

    """

    @classmethod
    def parse(cls, buf: bytes, params: Params) -> Tuple['String', bytes]:
        try:
            return QuotedString.parse(buf, params)
        except NotParseable:
            pass
        try:
            return LiteralString.parse(buf, params)
        except NotParseable:
            pass
        raise NotParseable(buf)

    @classmethod
    def build(cls, value: Any) -> Union[Nil, 'String']:
        """Produce either a :class:`QuotedString` or :class:`LiteralString`
        based on the contents of ``data``. This is useful to improve
        readability of response data.

        :param value: The string to serialize.

        """
        if value is None:
            return Nil()
        elif not value:
            return QuotedString(b'')
        elif isinstance(value, bytes):
            ascii_ = value
        elif hasattr(value, '__bytes__'):
            ascii_ = bytes(value)
        elif isinstance(value, str) or hasattr(value, '__str__'):
            value = str(value)
            try:
                ascii_ = bytes(value, 'ascii')
            except UnicodeEncodeError:
                ascii_ = bytes(value, 'utf-8')
                return LiteralString(ascii_)
        else:
            raise TypeError(value)
        if len(ascii_) < 32 and b'\n' not in ascii_:
            return QuotedString(ascii_)
        else:
            return LiteralString(ascii_)

    def __bytes__(self):
        raise NotImplementedError

    def __hash__(self):
        return hash((String, self.value))

    def __eq__(self, other):
        if isinstance(other, String):
            return self.value == other.value
        return NotImplemented


class QuotedString(String):
    """Represents a string object from an IMAP stream that was encased in
    double-quotes.

    """

    _quoted_pattern = re.compile(br'(\r|\n|\\.|\")')
    _quoted_specials_pattern = re.compile(br'[\"\\]')

    def __init__(self, string: bytes, raw: bytes = None) -> None:
        super().__init__()
        self.value = string
        self._raw = raw

    @classmethod
    def parse(cls, buf: bytes, params: Params) -> Tuple['QuotedString', bytes]:
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
                return cls(bytes(unquoted), quoted), buf[end:]
        raise NotParseable(buf)

    def __bytes__(self):
        if self._raw is not None:
            return bytes(self._raw)

        def escape_quoted_specials(match):
            return b'\\' + match.group(0)

        pat = self._quoted_specials_pattern
        quoted_string = pat.sub(escape_quoted_specials, self.value)
        self._raw = b'"%b"' % quoted_string
        return self._raw


class LiteralString(String):
    """Represents a string object from an IMAP stream that used the literal
    syntax.

    """

    _literal_pattern = re.compile(br'{(\d+)}\r?\n$')

    def __init__(self, string: bytes) -> None:
        super().__init__()
        self.value = string
        self._raw = None

    @classmethod
    def parse(cls, buf: bytes, params: Params) \
            -> Tuple['LiteralString', bytes]:
        start = cls._whitespace_length(buf)
        match = cls._literal_pattern.match(buf, start)
        if not match:
            raise NotParseable(buf)
        literal_length = int(match.group(1))
        if not params.continuations:
            raise RequiresContinuation(b'Literal string', literal_length)
        buf = params.continuations.pop(0)
        literal = buf[0:literal_length]
        if len(literal) != literal_length:
            raise NotParseable(buf)
        return cls(literal), buf[literal_length:]

    def __bytes__(self):
        if self._raw is not None:
            return bytes(self._raw)
        length_bytes = bytes(str(len(self.value)), 'ascii')
        self._raw = b'{%b}\r\n%b' % (length_bytes, self.value)
        return self._raw


class ListP(Primitive[Sequence[ParseableListType]]):
    """Represents a list of :class:`Parseable` objects from an IMAP stream."""

    _end_pattern = re.compile(br' *\)')

    def __init__(self, items: Iterable[ParseableListType],
                 sort: bool = False) -> None:
        super().__init__()
        if sort:
            self.value = sorted(items)
        else:
            self.value = list(items)

    def __iter__(self):
        return iter(self.value)

    @classmethod
    def parse(cls, buf: bytes, params: Params) \
            -> Tuple['ListP[Parseable]', bytes]:
        start = cls._whitespace_length(buf)
        if buf[start:start + 1] != b'(':
            raise NotParseable(buf)
        items: List[Parseable] = []
        buf = buf[start + 1:]
        while True:
            match = cls._end_pattern.match(buf)
            if match:
                return cls(items), buf[match.end(0):]
            elif items and not cls._whitespace_length(buf):
                raise NotParseable(buf)
            params_copy = params.copy(expected=params.list_expected)
            item, buf = Parseable.parse(buf, params_copy)
            items.append(item)

    def __bytes__(self):
        return b'(%b)' % b' '.join([bytes(item) for item in self.value])

    def __hash__(self):
        return hash((ListP, self.value))

    def __eq__(self, other):
        if isinstance(other, ListP):
            return self.__eq__(other.value)
        elif isinstance(other, SequenceABC):
            if len(self.value) != len(other):
                return False
            for i, val in enumerate(self.value):
                if val != other[i]:
                    return False
            return True
        return NotImplemented
