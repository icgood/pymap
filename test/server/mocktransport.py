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

    def __init__(self, matches, fd):
        self.queue = deque()
        self.matches = matches
        self.socket = _Socket(fd)

    @classmethod
    def _caller(cls, frame):
        return '{0}:{1!s}'.format(*inspect.getframeinfo(frame))

    def push_readline(self, data: bytes, wait=None, set=None) -> None:
        where = self._caller(inspect.currentframe().f_back)
        self.queue.append((_Type.READLINE, where, data, wait, set))

    def push_readexactly(self, data: bytes, wait=None, set=None) -> None:
        where = self._caller(inspect.currentframe().f_back)
        self.queue.append((_Type.READEXACTLY, where, data, wait, set))

    def push_write(self, *data, wait=None, set=None) -> None:
        where = self._caller(inspect.currentframe().f_back)
        self.queue.append((_Type.WRITE, where, data, None, None))
        self.queue.append((_Type.DRAIN, where, None, wait, set))

    def push_read_eof(self, wait=None, set=None):
        where = self._caller(inspect.currentframe().f_back)
        self.queue.append((_Type.READ_EOF, where, None, wait, set))

    def push_write_close(self, set=None):
        where = self._caller(inspect.currentframe().f_back)
        self.queue.append((_Type.WRITE_CLOSE, where, None, None, set))

    def push_login(self, wait=None, set=None):
        self.push_write(
            b'* OK [CAPABILITY IMAP4rev1 AUTH=PLAIN] Server ready ',
            (br'\S+', ), b'\r\n', wait=wait)
        self.push_readline(
            b'login1 LOGIN demouser demopass\r\n')
        self.push_write(
            b'login1 OK Authentication successful.\r\n', set=set)

    def push_logout(self, wait=None, set=None):
        self.push_readline(
            b'logout1 LOGOUT\r\n', wait=wait)
        self.push_write(
            b'* BYE Logging out.\r\n'
            b'logout1 OK Logout successful.\r\n')
        self.push_write_close(set=set)

    def push_select(self, mailbox, exists, recent, uidnext, unseen,
                    wait=None, set=None):
        self.push_readline(
            b'select1 SELECT ' + mailbox + b'\r\n', wait=wait)
        self.push_write(
            b'* OK [PERMANENTFLAGS (\\Answered \\Deleted \\Draft \\Flagged '
            b'\\Seen)] Flags permitted.\r\n* FLAGS (\\Answered \\Deleted '
            b'\\Draft \\Flagged \\Recent \\Seen)\r\n'
            b'* ', b'%i' % exists, b' EXISTS\r\n'
            b'* ', b'%i' % recent, b' RECENT\r\n'
            b'* OK [UIDNEXT ', b'%i' % uidnext, b'] Predicted next UID.\r\n'
            b'* OK [UIDVALIDITY ', (br'\d+', ), b'] Predicted next UID.\r\n'
            b'* OK [UNSEEN ', b'%i' % unseen, b'] First unseen message.\r\n'
            b'select1 OK [READ-WRITE] Selected mailbox.\r\n', set=set)

    def _pop_expected(self, got):
        try:
            type_, where, data, wait, set = self.queue.popleft()
        except IndexError:
            assert False, '\nExpected: <end>' + \
                          '\nGot:      ' + got.value
        assert type_ == got, '\nExpected: ' + type_.value + \
                             '\nGot:      ' + got.value + \
                             '\nWhere:    ' + where
        return data, wait, set

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
        data, wait, set = self._pop_expected(_Type.READLINE)
        if set:
            set.set()
        if wait:
            await wait.wait()
        return data

    async def readexactly(self, size: int) -> bytes:
        data, wait, set = self._pop_expected(_Type.READEXACTLY)
        assert size == len(data)
        if set:
            set.set()
        if wait:
            await wait.wait()
        return data

    def write(self, data: bytes) -> None:
        expected, _, _ = self._pop_expected(_Type.WRITE)
        self._match_write(expected, data)

    async def drain(self) -> None:
        _, wait, set = self._pop_expected(_Type.DRAIN)
        if set:
            set.set()
        if wait:
            await wait.wait()

    def at_eof(self):
        return False

    def close(self) -> None:
        _, _, set = self._pop_expected(_Type.WRITE_CLOSE)
        assert 0 == len(self.queue)
        if set:
            set.set()
