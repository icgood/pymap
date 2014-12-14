# Copyright (c) 2014 Ian C. Good
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
import base64

from . import Parseable, NotParseable

__all__ = ['Primitive', 'Nil', 'Number', 'Atom', 'List',
           'String', 'QuotedString', 'LiteralString']


class Primitive(Parseable):
    """Represents a primitive data object from an IMAP stream. The sub-classes
    implement the different primitive formats.

    """

    _atom_pattern = re.compile(br'[\x21\x23\x24\x26\x27\x2B'
                               br'-\x5B\x5E-\x7A\x7C\x7E]+')
    _nil_pattern = re.compile(b'^NIL$', re.I)
    _num_pattern = re.compile(b'^\d+$')


class Nil(Primitive):
    """Represents a NIL object from an IMAP stream.

    """

    def __init__(self):
        super(Nil, self).__init__()
        self.value = None

    @classmethod
    def try_parse(cls, buf, start=0):
        start += cls._whitespace_length(buf, start)
        match = cls._atom_pattern.match(buf, start)
        if not match:
            raise NotParseable(buf)
        atom = match.group(0)
        if not cls._nil_pattern.match(atom):
            raise NotParseable(buf)
        return cls(), match.end(0)

    def __bytes__(self):
        return b'NIL'

Parseable.register_type(Nil)


class Number(Primitive):
    """Represents a number object from an IMAP stream.

    :param int num: The number for the datum.

    """

    def __init__(self, num):
        super(Number, self).__init__()
        self.value = num

    @classmethod
    def try_parse(cls, buf, start=0):
        start += cls._whitespace_length(buf, start)
        match = cls._atom_pattern.match(buf, start)
        if not match:
            raise NotParseable(buf)
        atom = match.group(0)
        if not cls._num_pattern.match(atom):
            raise NotParseable(buf)
        return cls(int(match.group(0))), match.end(0)

    def __bytes__(self):
        return bytes(str(self.value).encode('ascii'))

Parseable.register_type(Number)


class Atom(Primitive):
    """Represents an atom object from an IMAP stream.

    """

    def __init__(self, value):
        super(Atom, self).__init__()
        self.value = value

    @classmethod
    def try_parse(cls, buf, start=0):
        start += cls._whitespace_length(buf, start)
        match = cls._atom_pattern.match(buf, start)
        if not match:
            raise NotParseable(buf)
        atom = match.group(0)
        if cls._nil_pattern.match(atom):
            raise NotParseable(buf)
        elif cls._num_pattern.match(atom):
            raise NotParseable(buf)
        return cls(atom), match.end(0)

    def __bytes__(self):
        return bytes(self.value)

Parseable.register_type(Atom)


class String(Primitive):
    """Represents a string object from an IMAP string. This object may not be
    instantiated directly, use one of its derivitives instead.

    """

    def __init__(self):
        raise NotImplementedError()

    @classmethod
    def try_parse(cls, buf, start=0):
        start += cls._whitespace_length(buf, start)
        try:
            return QuotedString._try_parse(buf, start)
        except NotParseable:
            pass
        try:
            return LiteralString._try_parse(buf, start)
        except NotParseable:
            pass
        raise NotParseable(buf)

Parseable.register_type(String)


class QuotedString(String):
    """Represents a string object from an IMAP stream that was encased in
    double-quotes.

    :param bytes string: The raw string for the datum.
    :param bytes raw: When parsed from an IMAP stream, this contains a copy of
                      the double-quoted and escaped version of the string for
                      reuse.

    """

    _quoted_pattern = re.compile(br'(\r|\n|\\.|\")')

    def __init__(self, string, raw=None):
        self.value = string
        if raw is not None:
            self._raw = raw
        else:
            quoted_specials = re.compile(br'[\"\\]')

            def escape_quoted_specials(match):
                return b'\\' + match.group(0)
            quoted_string = re.sub(quoted_specials, escape_quoted_specials,
                                   string)
            self._raw = b'"' + quoted_string + b'"'

    @classmethod
    def _try_parse(cls, buf, start):
        if buf[start:start+1] != b'"':
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
                quoted = buf[start:end+1]
                return cls(bytes(unquoted), quoted), end
        raise NotParseable(buf)

    def __bytes__(self):
        return self._raw


class LiteralString(String):
    """Represents a string object from an IMAP stream that used the literal
    syntax.

    :param bytes string: The raw string for the datum.
    :param bytes raw: When parsed from an IMAP stream, this contains a copy of
                      the double-quoted and escaped version of the string for
                      reuse.

    """

    _literal_pattern = re.compile(br'\{(\d+)\}\r?\n')

    def __init__(self, string, raw=None):
        self.value = string
        if raw is not None:
            self._raw = raw
        else:
            length_bytes = bytes(str(len(self.value)).encode('ascii'))
            literal_header = b'{' + length_bytes + b'}\r\n'
            self._raw = literal_header + self.value

    @classmethod
    def _try_parse(cls, buf, start):
        match = cls._literal_pattern.match(buf, start)
        if not match:
            raise NotParseable(buf)
        literal_start = match.end(0)
        literal_length = int(match.group(1))
        literal_end = literal_start + literal_length
        literal = buf[literal_start:literal_end]
        raw = buf[start:literal_end]
        if len(literal) != literal_length:
            raise NotParseable(buf)
        return cls(literal, raw), literal_end

    def __bytes__(self):
        return self._raw


class List(Primitive):
    """Represents a list of :class:`Parseable` objects from an IMAP stream.

    :param items: Iterable of items, collected into a list, that make up the
                  datum.
    :type items: collections.abc.Iterable

    """

    def __init__(self, items):
        super(List, self).__init__()
        self.value = list(items)

    @classmethod
    def try_parse(cls, buf, start=0):
        start += cls._whitespace_length(buf, start)
        if buf[start:start+1] != b'(':
            raise NotParseable(buf)
        elif buf[start:start+2] == b'()':
            return cls([]), start+2
        items = []
        cur = start+1
        while True:
            item, cur = Parseable.try_parse(buf, cur)
            items.append(item)
            if buf[cur:cur+1] == b')':
                return cls(items), cur + 1
            white_len = cls._whitespace_length(buf, cur)
            if not white_len:
                raise NotParseable(buf)
            cur += white_len

    def __bytes__(self):
        return b'(' + b' '.join([bytes(item) for item in self.value]) + b')'

Parseable.register_type(List)
