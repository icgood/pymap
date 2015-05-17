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

from .. import NotParseable
from . import Special

__all__ = ['Tag']


class Tag(Special):
    """Represents the tag prefixed to every client command in an IMAP stream.

    :param bytes tag: The contents of the tag.

    """

    _pattern = re.compile(br'[\x21\x23\x24\x26\x27\x2C-\x5B'
                          br'\x5D\x5E-\x7A\x7C\x7E]+')

    def __init__(self, tag):
        super().__init__()
        self.value = tag

    @classmethod
    def parse(cls, buf, **kwargs):
        buf = memoryview(buf)
        start = cls._whitespace_length(buf)
        match = cls._pattern.match(buf, start)
        if not match:
            raise NotParseable(buf)
        return cls(match.group(0)), buf[match.end(0):]

    def __bytes__(self):
        return self.value
