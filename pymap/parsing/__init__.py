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
from enum import Enum

from pymap.core import PymapError

__all__ = ['NotParseable', 'Parseable', 'EndLine']


class NotParseable(PymapError):
    """Indicates that the given buffer was not parseable by one or all of the
    data formats.

    :param bytes buf: The buffer with the parsing error.
    :param int where: The index where the parsing error started.

    """

    def __init__(self, buf, where=None):
        super(NotParseable, self).__init__(buf)
        self.where = where


class Parseable(object):
    """Represents a parseable data object from an IMAP stream. The sub-classes
    implement the different data formats.

    This base class will be inherited by all necessary entries in the IMAP
    formal syntax section.

    """

    _known_parseables = []
    _whitespace_pattern = re.compile(br' +')

    @classmethod
    def register_type(cls, type_class):
        cls._known_parseables.append(type_class)

    @classmethod
    def _whitespace_length(cls, buf, start=0):
        match = cls._whitespace_pattern.match(buf, start)
        if match:
            return match.end(0) - start
        return 0

    @classmethod
    def _enforce_whitespace(cls, buf, start=0):
        ret = cls._whitespace_length(buf, start)
        if not ret:
            raise NotParseable(buf)
        return buf[start+ret:]

    @classmethod
    def parse(cls, buf, continuation=None, expected=None):
        expected = expected or cls._known_parseables
        for data_type in expected:
            try:
                return data_type.parse(buf, continuation=continuation)
            except NotParseable:
                pass
        raise NotParseable(buf)


class EndLine(Parseable):
    """Represents the end of a parsed line. This will only parse if the buffer
    has zero or more space characters followed by a new-line sequence.

    """

    _pattern = re.compile(br' *\r?\n')

    @classmethod
    def parse(cls, buf):
        spaces = cls._whitespace_length(buf)
        match = cls._pattern.search(buf, spaces)
        if not match:
            raise NotParseable(buf, spaces)
        remaining = buf[spaces:match.start(0)]
        if remaining:
            raise NotParseable(buf, spaces)
        return cls(), buf[match.end(0):]

    def __bytes__(self):
        return b'\r\n'
