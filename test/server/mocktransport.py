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
import inspect
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


class _Socket:

    def __init__(self, fd: int):
        self.fd = fd

    def fileno(self):
        return self.fd


class MockTransport:

    def __init__(self, matches):
        self.queue = deque()
        self.matches = matches
        self.socket = _Socket(1)

    @classmethod
    def _caller(cls, frame):
        return '{0}:{1!s}'.format(*inspect.getframeinfo(frame))

    def push_readline(self, data: bytes) -> None:
        frame = inspect.currentframe().f_back
        self.queue.append((_Type.READLINE, data, self._caller(frame)))

    def push_readexactly(self, data: bytes) -> None:
        frame = inspect.currentframe().f_back
        self.queue.append((_Type.READEXACTLY, data, self._caller(frame)))

    def push_write(self, *data) -> None:
        frame = inspect.currentframe().f_back
        self.queue.append((_Type.WRITE, data, self._caller(frame)))
        self.queue.append((_Type.DRAIN, None, self._caller(frame)))

    def push_read_eof(self):
        frame = inspect.currentframe().f_back
        self.queue.append((_Type.READ_EOF, None, self._caller(frame)))

    def push_write_close(self):
        frame = inspect.currentframe().f_back
        self.queue.append((_Type.WRITE_CLOSE, None, self._caller(frame)))

    def _pop_expected(self, got):
        try:
            type_, data, where = self.queue.popleft()
        except IndexError:
            assert False, '\nExpected: <end>' + \
                          '\nGot:      ' + got.value
        assert type_ == got, '\nExpected: ' + type_.value + \
                             '\nGot:      ' + got.value + \
                             '\nWhere:    ' + where
        return data

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

    def get_extra_info(self, name: str):
        if name == 'socket':
            return self.socket

    async def readline(self) -> bytes:
        return self._pop_expected(_Type.READLINE)

    async def readexactly(self, size: int) -> bytes:
        data = self._pop_expected(_Type.READEXACTLY)
        assert size == len(data)
        return data

    def write(self, data: bytes) -> None:
        expected = self._pop_expected(_Type.WRITE)
        self._match_write(expected, data)

    async def drain(self) -> None:
        self._pop_expected(_Type.DRAIN)

    def at_eof(self):
        return False

    def close(self) -> None:
        self._pop_expected(_Type.WRITE_CLOSE)
        assert 0 == len(self.queue)
