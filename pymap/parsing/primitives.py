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

from pymap.core import PymapError


class NotParseable(PymapError):
    """Indicates that the given buffer was not parseable by one or all of the
    data formats.

    """
    pass


class Primitive(object):
    """Represents a primitive data object from an IMAP stream. The sub-classes
    implement the different data formats.

    """

    _whitespace_pattern = re.compile(rb'\s+')

    @classmethod
    def _whitespace_length(cls, buf, start):
        match = cls._whitespace_pattern.match(buf, start)
        if match:
            return match.end(0) - start
        return 0

    @property
    def value(self):
        return self._val

    @classmethod
    def try_parse(cls, buf, start=0, expected=None):
        expected = expected or \
            [Nil, Number, Atom, String, List]
        for prim_type in expected:
            try:
                return prim_type.try_parse(buf, start)
            except NotParseable:
                pass
        raise NotParseable(buf)


class Nil(Primitive):
    """Represents a NIL object from an IMAP stream.

    """

    _pattern = re.compile(rb'[nN][iI][lL]')

    def __init__(self):
        super(Nil, self).__init__()
        self._val = None

    @classmethod
    def try_parse(cls, buf, start=0):
        start += cls._whitespace_length(buf, start)
        match = cls._pattern.match(buf, start)
        if not match:
            raise NotParseable(buf)
        return cls(), match.end(0)

    def __bytes__(self):
        return b'NIL'


class Number(Primitive):
    """Represents a number object from an IMAP stream.

    :param int num: The number for the datum.

    """

    _pattern = re.compile(rb'(\d+)')

    def __init__(self, num):
        super(Number, self).__init__()
        self._val = num

    @classmethod
    def try_parse(cls, buf, start=0):
        start += cls._whitespace_length(buf, start)
        match = cls._pattern.match(buf, start)
        if not match:
            raise NotParseable(buf)
        return cls(int(match.group(1))), match.end(1)

    def __bytes__(self):
        return bytes(str(self._val).encode('ascii'))


class Atom(Primitive):
    """Represents an atom object from an IMAP stream.

    """

    _pattern = re.compile(rb'[^\(\)\{ \"\\\]\%\*\x00-\x32\x7F]+')

    def __init__(self, value):
        super(Atom, self).__init__()
        self._val = value

    @classmethod
    def try_parse(cls, buf, start=0):
        start += cls._whitespace_length(buf, start)
        match = cls._pattern.match(buf, start)
        if not match:
            raise NotParseable(buf)
        return cls(match.group(0)), match.end(0)

    def __bytes__(self):
        return bytes(self._val)


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


class QuotedString(String):
    """Represents a string object from an IMAP stream that was encased in
    double-quotes.

    :param bytes string: The raw string for the datum.
    :param bytes raw: When parsed from an IMAP stream, this contains a copy of
                      the double-quoted and escaped version of the string for
                      reuse.

    """

    _quoted_pattern = re.compile(rb'(\r|\n|\\.|\")')

    def __init__(self, string, raw=None):
        self._val = string
        if raw is not None:
            self._raw = raw
        else:
            quoted_specials = re.compile(rb'[\"\\]')
            quoted_string = re.sub(quoted_specials, rb'\\0', string)
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
                return cls(bytes(unquoted), quoted), end+1
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

    _literal_pattern = re.compile(rb'\{(\d+)\}\r?\n')

    def __init__(self, string, raw=None):
        self._val = string
        if raw is not None:
            self._raw = raw
        else:
            length_bytes = bytes(str(len(self._val)).encode('ascii'))
            literal_header = b'{' + length_bytes + b'}\r\n'
            self._raw = literal_header + self._val

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
    """Represents a list of :class:`Primitive` objects from an IMAP stream.

    :param items: Iterable of items, collected into a list, that make up the
                  datum.
    :type items: collections.abc.Iterable

    """

    def __init__(self, items):
        super(List, self).__init__()
        self._val = list(items)

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
            item, cur = Primitive.try_parse(buf, cur)
            items.append(item)
            if buf[cur:cur+1] == b')':
                return cls(items), cur + 1
            white_len = cls._whitespace_length(buf, cur)
            if not white_len:
                raise NotParseable(buf)
            cur += white_len

    def __bytes__(self):
        return b'(' + b' '.join([bytes(item) for item in self._val]) + b')'
