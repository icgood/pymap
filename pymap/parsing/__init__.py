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

from pymap.core import PymapError

__all__ = ['RequiresContinuation', 'NotParseable', 'UnexpectedType',
           'Parseable', 'Space', 'EndLine']


class RequiresContinuation(PymapError):
    """Indicates that the buffer has been successfully parsed so far, but
    requires a continuation of the command from the client.

    :param bytes message: The message from the server.
    :param int literal_length: If the continuation is for a string literal,
                               this is the byte length to expect.

    """

    def __init__(self, message, literal_length=0):
        super().__init__()
        self.message = message
        self.literal_length = literal_length


class NotParseable(PymapError):
    """Indicates that the given buffer was not parseable by one or all of the
    data formats.

    :param bytes buf: The buffer with the parsing error.
    :param int where: The index where the parsing error started.

    """

    error_indicator = b'[:ERROR:]'

    def __init__(self, buf):
        super().__init__()
        self.buf = buf
        if isinstance(buf, memoryview):
            self.offset = offset = len(buf.obj) - buf.nbytes
        else:
            self.offset = 0


    @property
    def before(self):
        if hasattr(self, '_before'):
            return self._before
        buf = self.buf
        if isinstance(self.buf, memoryview):
            buf = buf.obj
        self._before = before = buf[0:self.offset]
        return before

    @property
    def after(self):
        if hasattr(self, '_after'):
            return self._after
        if isinstance(self.buf, memoryview):
            self._after = after = self.buf.tobytes()
        else:
            self._after = after = self.buf
        return after

    def __bytes__(self):
        if hasattr(self, '_raw'):
            return self._raw
        before = self.before
        after = self.after.rstrip(b'\r\n')
        self._raw = raw = self.error_indicator.join((before, after))
        return raw

    def __str__(self):
        return str(bytes(self), 'ascii', 'replace')


class UnexpectedType(NotParseable):
    """Indicates that a generic parseable that was given a sub-type expectation
    failed to meet that expectation.

    """
    pass


class Parseable(object):
    """Represents a parseable data object from an IMAP stream. The sub-classes
    implement the different data formats.

    This base class will be inherited by all necessary entries in the IMAP
    formal syntax section.

    """

    _whitespace_pattern = re.compile(br' +')

    @classmethod
    def _whitespace_length(cls, buf, start=0):
        match = cls._whitespace_pattern.match(buf, start)
        if match:
            return match.end(0) - start
        return 0

    @classmethod
    def parse(cls, buf, expected, **kwargs):
        buf = memoryview(buf)
        for data_type in expected:
            try:
                return data_type.parse(buf, **kwargs)
            except NotParseable:
                pass
        raise UnexpectedType(buf)


class Space(Parseable):
    """Represents at least one space character.

    :param int length: The number of consecutive space characters.

    """

    def __init__(self, length):
        super().__init__()
        self.length = length

    @classmethod
    def parse(cls, buf, **kwargs):
        buf = memoryview(buf)
        ret = cls._whitespace_length(buf)
        if not ret:
            raise NotParseable(buf)
        return cls(ret), buf[ret:]

    def __bytes__(self):
        return b' ' * self.length


class EndLine(Parseable):
    """Represents the end of a parsed line. This will only parse if the buffer
    has zero or more space characters followed by a new-line sequence.

    """

    _pattern = re.compile(br' *(\r?)\n')

    def __init__(self, preceding_spaces=0, carriage_return=True):
        super().__init__()
        self.preceding_spaces = preceding_spaces
        self.carriage_return = carriage_return

    @classmethod
    def parse(cls, buf):
        buf = memoryview(buf)
        match = cls._pattern.match(buf)
        if not match:
            raise NotParseable(buf)
        preceding_spaces = match.start(1)
        carriage_return = bool(match.group(1))
        return cls(preceding_spaces, carriage_return), buf[match.end(0):]

    def __bytes__(self):
        endl = b'\r\n' if self.carriage_return else b'\n'
        return b' ' * self.preceding_spaces + endl
