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

from ..primitives import String, QuotedString
from . import Special

__all__ = ['AString']


class AString(Special):
    """Represents a string that may have quotes (like a quoted-string) or may
    not (like an atom).  Additionally allows the closing square bracket (``]``)
    character in the unquoted form.

    :param bytes string: The parsed string.

    """

    _pattern = re.compile(br'[\x21\x23\x24\x26\x27\x2B-\x5B'
                          br'\x5D\x5E-\x7A\x7C\x7E]+')

    def __init__(self, string, raw=None):
        super().__init__()
        self.value = string
        self._raw = raw

    @classmethod
    def parse(cls, buf, **kwargs):
        buf = memoryview(buf)
        start = cls._whitespace_length(buf)
        match = cls._pattern.match(buf, start)
        if match:
            buf = buf[match.end(0):]
            return cls(match.group(0), match.group(0)), buf
        string, buf = String.parse(buf, **kwargs)
        return cls(string.value, bytes(string)), buf

    def __bytes__(self):
        if self._raw is not None:
            return self._raw
        match = self._pattern.fullmatch(self.value)
        if match:
            return self.value
        else:
            return bytes(QuotedString(self.value))
