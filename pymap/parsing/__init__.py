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
from typing import Tuple, Optional, Generic, Sequence, Dict, Any, List, Type

from .typing import ParseableType

__all__ = ['RequiresContinuation', 'NotParseable', 'InvalidContent',
           'UnexpectedType', 'Parseable', 'Space', 'EndLine', 'Primitive',
           'Special', 'Params']


class RequiresContinuation(Exception):
    """Indicates that the buffer has been successfully parsed so far, but
    requires a continuation of the command from the client.

    :param message: The message from the server.
    :param literal_length: If the continuation is for a string literal,
                           this is the byte length to expect.

    """

    def __init__(self, message: bytes, literal_length: int = 0) -> None:
        super().__init__()
        self.message = message
        self.literal_length = literal_length


class NotParseable(Exception):
    """Indicates that the given buffer was not parseable by one or all of the
    data formats.

    :param buf: The buffer with the parsing error.

    """

    error_indicator = b'[:ERROR:]'

    def __init__(self, buf: bytes) -> None:
        super().__init__()
        self.buf = buf
        self._raw = None
        self._before: Optional[bytes] = None
        self._after: Optional[bytes] = None
        self.offset: int = 0
        if isinstance(buf, memoryview):
            obj = getattr(buf, 'obj')
            nbytes = getattr(buf, 'nbytes')
            self.offset = len(obj) - nbytes

    @property
    def before(self) -> bytes:
        if self._before is not None:
            return self._before
        buf = self.buf
        if isinstance(buf, memoryview):
            buf = getattr(buf, 'obj')
        self._before = before = buf[0:self.offset]
        return before

    @property
    def after(self) -> bytes:
        if self._after is not None:
            return self._after
        if isinstance(self.buf, memoryview):
            self._after = after = self.buf.tobytes()
        else:
            self._after = after = self.buf
        return after

    def __bytes__(self):
        if self._raw is not None:
            return self._raw
        before = self.before
        after = self.after.rstrip(b'\r\n')
        self._raw = raw = self.error_indicator.join((before, after))
        return raw

    def __str__(self):
        return str(bytes(self), 'ascii', 'replace')


class InvalidContent(NotParseable, ValueError):
    """Indicates the type of the parsed content was correct, but something
    about the content did not fit what was expected by the special type.

    """
    pass


class UnexpectedType(NotParseable):
    """Indicates that a generic parseable that was given a sub-type expectation
    failed to meet that expectation.

    """
    pass


class Params:
    """Parameters used and passed around among the :meth:`~Parseable.parse`
    methods.

    """

    __slots__ = ['continuations', 'expected', 'list_expected',
                 'uid', 'charset', 'tag']

    def __init__(self, continuations: List[bytes] = None,
                 expected: Sequence[Type['Parseable']] = None,
                 list_expected: Sequence[Type['Parseable']] = None,
                 uid: bool = False,
                 charset: str = None,
                 tag: bytes = None) -> None:
        self.continuations = continuations or []
        self.expected = expected or []
        self.list_expected = list_expected or []
        self.uid = uid
        self.charset = charset
        self.tag = tag or b'.'

    def _set_if_none(self, kwargs, attr, value):
        if value is not None:
            kwargs[attr] = value
        else:
            kwargs[attr] = getattr(self, attr)

    def copy(self, continuations: Sequence['Parseable'] = None,
             expected: Sequence[Type['Parseable']] = None,
             list_expected: Sequence[Type['Parseable']] = None,
             uid: bool = None,
             charset: str = None,
             tag: bytes = None) -> 'Params':
        kwargs: Dict[str, Any] = {}
        self._set_if_none(kwargs, 'continuations', continuations)
        self._set_if_none(kwargs, 'expected', expected)
        self._set_if_none(kwargs, 'list_expected', list_expected)
        self._set_if_none(kwargs, 'uid', uid)
        self._set_if_none(kwargs, 'charset', charset)
        self._set_if_none(kwargs, 'tag', tag)
        return Params(**kwargs)


class Parseable(Generic[ParseableType]):
    """Represents a parseable data object from an IMAP stream. The sub-classes
    implement the different data formats.

    This base class will be inherited by all necessary entries in the IMAP
    formal syntax section.

    """

    _whitespace_pattern = re.compile(br' +')

    def __init__(self):
        super().__init__()
        self.value: ParseableType = None

    @classmethod
    def _whitespace_length(cls, buf, start=0) -> int:
        match = cls._whitespace_pattern.match(buf, start)
        if match:
            return match.end(0) - start
        return 0

    def __bytes__(self):
        raise NotImplementedError

    @classmethod
    def parse(cls, buf: bytes, params: 'Params') -> Tuple['Parseable', bytes]:
        for data_type in params.expected:
            try:
                return data_type.parse(buf, params)
            except NotParseable:
                pass
        raise UnexpectedType(buf)


class Space(Parseable[None]):
    """Represents at least one space character.

    """

    def __init__(self, length: int) -> None:
        super().__init__()
        self.length = length

    @classmethod
    def parse(cls, buf: bytes, params: 'Params') -> Tuple['Space', bytes]:
        ret = cls._whitespace_length(buf)
        if not ret:
            raise NotParseable(buf)
        return cls(ret), buf[ret:]

    def __bytes__(self):
        return b' ' * self.length


class EndLine(Parseable[None]):
    """Represents the end of a parsed line. This will only parse if the buffer
    has zero or more space characters followed by a new-line sequence.

    """

    _pattern = re.compile(br' *(\r?)\n')

    def __init__(self, preceding_spaces: int = 0,
                 carriage_return: bool = True) -> None:
        super().__init__()
        self.preceding_spaces = preceding_spaces
        self.carriage_return = carriage_return

    @classmethod
    def parse(cls, buf: bytes, params: 'Params') -> Tuple['EndLine', bytes]:
        match = cls._pattern.match(buf)
        if not match:
            raise NotParseable(buf)
        preceding_spaces = match.start(1)
        carriage_return = bool(match.group(1))
        return cls(preceding_spaces, carriage_return), buf[match.end(0):]

    def __bytes__(self):
        endl = b'\r\n' if self.carriage_return else b'\n'
        return b' ' * self.preceding_spaces + endl


class Primitive(Parseable[ParseableType]):
    """Represents a primitive data object from an IMAP stream. The sub-classes
    implement the different primitive formats.

    """

    _atom_pattern = re.compile(br'[\x21\x23\x24\x26\x27\x2B'
                               br'-\x5B\x5E-\x7A\x7C\x7E]+')

    def __bytes__(self):
        raise NotImplementedError


class Special(Parseable[ParseableType]):
    """Base class for special data objects in an IMAP stream."""

    def __bytes__(self):
        raise NotImplementedError
