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

from datetime import datetime
from typing import Tuple

from .. import Params, Special, InvalidContent
from ..primitives import QuotedString

__all__ = ['DateTime']


class DateTime(Special[datetime]):
    """Represents a date-time quoted string from an IMAP stream."""

    def __init__(self, when: datetime, raw: bytes = None) -> None:
        super().__init__()
        self.value = when
        self._raw = raw

    @classmethod
    def parse(cls, buf: bytes, params: Params) -> Tuple['DateTime', bytes]:
        string, after = QuotedString.parse(buf, params)
        try:
            when_str = str(string.value, 'ascii')
            when = datetime.strptime(when_str, '%d-%b-%Y %X %z')
        except (UnicodeDecodeError, ValueError):
            raise InvalidContent(buf)
        return cls(when, string.value), after

    def __bytes__(self):
        if self._raw is None:
            if self.value.tzinfo is None:
                raw_str = self.value.strftime('%d-%b-%Y %X')
            else:
                raw_str = self.value.strftime('%d-%b-%Y %X %z')
            self._raw = bytes(raw_str, 'ascii')
        return b'"%b"' % self._raw
