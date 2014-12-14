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

__all__ = ['NotParseable', 'Parseable']


class NotParseable(PymapError):
    """Indicates that the given buffer was not parseable by one or all of the
    data formats.

    """
    pass


class Parseable(object):
    """Represents a parseable data object from an IMAP stream. The sub-classes
    implement the different data formats.

    This base class will be inherited by all necessary entries in the IMAP
    formal syntax section.

    """

    _known_parseables = []
    _whitespace_pattern = re.compile(br' +')
    _newline_pattern = re.compile(br'\r?\n')

    @classmethod
    def register_type(cls, type_class):
        cls._known_parseables.append(type_class)

    @classmethod
    def _whitespace_length(cls, buf, start):
        match = cls._whitespace_pattern.match(buf, start)
        if match:
            return match.end(0) - start
        return 0

    @classmethod
    def _line_match(cls, buf, start):
        match = cls._newline_pattern.search(buf, start)
        if not match:
            raise NotParseable(buf)
        remaining = buf[start:match.start(0)]
        return remaining, match.end(0)

    @classmethod
    def _enforce_whitespace(cls, buf, start):
        ret = cls._whitespace_length(buf, start)
        if not ret:
            raise NotParseable(buf)
        return start + ret

    @classmethod
    def try_parse(cls, buf, start=0, expected=None):
        expected = expected or cls._known_parseables
        for data_type in expected:
            try:
                return data_type.try_parse(buf, start)
            except NotParseable:
                pass
        raise NotParseable(buf)
