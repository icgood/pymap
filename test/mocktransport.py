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

import enum
import re
from collections import deque

__all__ = ['MockTransport']


class _Type(enum.Enum):
    READLINE = "reader.readline()"
    READEXACTLY = "reader.readexactly()"
    WRITE = "writer.write()"
    DRAIN = "writer.drain()"
    READ_EOF = "reader.at_eof()"
    WRITE_CLOSE = "writer.close()"


class MockTransport:

    def __init__(self):
        self.queue = deque()
        self.matches = {}

    def push_readline(self, data: bytes) -> None:
        self.queue.append((_Type.READLINE, data))

    def push_readexactly(self, data: bytes) -> None:
        self.queue.append((_Type.READEXACTLY, data))

    def push_write(self, *data) -> None:
        self.queue.append((_Type.WRITE, data))
        self.queue.append((_Type.DRAIN, None))

    def push_read_eof(self):
        self.queue.append((_Type.READ_EOF, None))

    def push_write_close(self):
        self.queue.append((_Type.WRITE_CLOSE, None))

    @classmethod
    def _check_type(cls, expected, got):
        assert expected == got, '\nExpected: ' + expected.value + \
                                '\nGot:      ' + got.value

    def _match_write(self, expected, data):
        re_parts = []
        for part in expected:
            if isinstance(part, bytes):
                re_parts.append(re.escape(part))
            else:
                if len(part) == 1:
                    re_parts.append(part[0])
                else:
                    regex, name = part
                    re_parts.append(br'(?P<' + name + br'>' + regex + br')')
        full_regex = b'^' + b''.join(re_parts) + b'$'
        match = re.search(full_regex, data)
        assert match, '\nExpected: ' + repr(expected) + \
                      '\nGot:      ' + repr((data, )) + \
                      '\nRegex:    ' + str(full_regex, 'ascii')
        self.matches.update(match.groupdict())

    async def readline(self) -> bytes:
        type_, expected = self.queue.popleft()
        self._check_type(_Type.READLINE, type_)
        return expected

    async def readexactly(self, _: int) -> bytes:
        type_, expected = self.queue.popleft()
        self._check_type(_Type.READEXACTLY, type_)
        return expected

    def write(self, data: bytes) -> None:
        type_, expected = self.queue.popleft()
        self._check_type(_Type.WRITE, type_)
        self._match_write(expected, data)

    async def drain(self) -> None:
        type_, _ = self.queue.popleft()
        self._check_type(_Type.DRAIN, type_)

    def at_eof(self):
        expect = self.queue.popleft()
        if expect[0] != _Type.READ_EOF:
            self.queue.appendleft(expect)
            return False
        return True

    def close(self) -> None:
        type_, _ = self.queue.popleft()
        self._check_type(_Type.WRITE_CLOSE, type_)
        assert 0 == len(self.queue)
