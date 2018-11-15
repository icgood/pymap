import asyncio
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

    def __init__(self, fd: int) -> None:
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
        frame = frame.f_back if frame else None
        fields = inspect.getframeinfo(frame) if frame else ('?', '?')
        return '{0}:{1!s}'.format(fields[0], fields[1])

    def push_readline(self, data: bytes, wait=None, set=None) -> None:
        where = self._caller(inspect.currentframe())
        self.queue.append((_Type.READLINE, where, data, wait, set))

    def push_readexactly(self, data: bytes, wait=None, set=None) -> None:
        where = self._caller(inspect.currentframe())
        self.queue.append((_Type.READEXACTLY, where, data, wait, set))

    def push_write(self, *data, wait=None, set=None) -> None:
        where = self._caller(inspect.currentframe())
        self.queue.append((_Type.WRITE, where, data, None, None))
        self.queue.append((_Type.DRAIN, where, None, wait, set))

    def push_read_eof(self, wait=None, set=None):
        where = self._caller(inspect.currentframe())
        self.queue.append((_Type.READ_EOF, where, None, wait, set))

    def push_write_close(self, set=None):
        where = self._caller(inspect.currentframe())
        self.queue.append((_Type.WRITE_CLOSE, where, None, None, set))

    def push_login(self, wait=None, set=None):
        self.push_write(
            b'* OK [CAPABILITY IMAP4rev1',
            (br'(?:\s+[a-zA-Z0-9=+-]+)*', ),
            b'] Server ready ',
            (br'\S+', ), b'\r\n', wait=wait)
        self.push_readline(
            b'login1 LOGIN testuser testpass\r\n')
        self.push_write(
            b'login1 OK Authentication successful.\r\n', set=set)

    def push_logout(self, wait=None, set=None):
        self.push_readline(
            b'logout1 LOGOUT\r\n', wait=wait)
        self.push_write(
            b'* BYE Logging out.\r\n'
            b'logout1 OK Logout successful.\r\n')
        self.push_write_close(set=set)

    def push_select(self, mailbox, exists=None, recent=None, uidnext=None,
                    unseen=None, wait=None, post_wait=None, set=None):
        if unseen is False:
            unseen_line = (None, b'')
        else:
            unseen_line = (None, b'* OK [UNSEEN ', (br'\d+', ),
                           b'] First unseen message.\r\n')
        if exists is None:
            exists = (br'\d+', )
        if recent is None:
            recent = (br'\d+', )
        if uidnext is None:
            uidnext = (br'\d+', )
        self.push_readline(
            b'select1 SELECT ' + mailbox + b'\r\n', wait=wait)
        self.push_write(
            b'* OK [PERMANENTFLAGS (\\Answered \\Deleted \\Draft \\Flagged '
            b'\\Seen)] Flags permitted.\r\n* FLAGS (\\Answered \\Deleted '
            b'\\Draft \\Flagged \\Recent \\Seen)\r\n'
            b'* ', exists, b' EXISTS\r\n'
            b'* ', recent, b' RECENT\r\n'
            b'* OK [UIDNEXT ', uidnext, b'] Predicted next UID.\r\n'
            b'* OK [UIDVALIDITY ', (br'\d+', ), b'] UIDs valid.\r\n',
            unseen_line,
            b'select1 OK [READ-WRITE] Selected mailbox.\r\n',
            wait=post_wait, set=set)

    def _pop_expected(self, got):
        try:
            type_, where, data, wait, set = self.queue.popleft()
        except IndexError:
            assert False, '\nExpected: <end>' + \
                          '\nGot:      ' + got.value
        assert type_ == got, '\nExpected: ' + type_.value + \
                             '\nGot:      ' + got.value + \
                             '\nWhere:    ' + where
        return where, data, wait, set

    def _match_write_expected(self, expected, re_parts):
        for part in expected:
            if part is None:
                re_parts.append(br'.*?')
            elif isinstance(part, bytes):
                re_parts.append(re.escape(part))
            elif isinstance(part, int):
                re_parts.append(b'%i' % part)
            else:
                if len(part) == 1:
                    re_parts.append(part[0])
                elif part[0] is None:
                    self._match_write_expected(part[1:], re_parts)
                else:
                    regex, name = part
                    re_parts.append(br'(?P<' + name + br'>' + regex + br')')

    def _match_write_msg(self, expected, data, full_regex, where):
        parts = ['',
                 'Expected: ' + repr(expected),
                 'Got:      ' + repr((data, )),
                 'Where:    ' + where,
                 '---------------------------------------------------']
        raw_regex = str(full_regex.replace(b'\r', b''), 'ascii').splitlines()
        raw_data = str(data, 'ascii', 'replace').splitlines()
        for regex_line, data_line in zip(raw_regex, raw_data):
            parts.append('regex: ' + regex_line.lstrip('^'))
            parts.append('data:  ' + re.escape(data_line + '\\'))
            parts.append('')
        return '\n'.join(parts)

    def _match_write(self, where, expected, data):
        re_parts = []
        self._match_write_expected(expected, re_parts)
        full_regex = b'^' + b''.join(re_parts) + b'$'
        match = re.search(full_regex, data)
        assert match, self._match_write_msg(expected, data, full_regex, where)
        self.matches.update(match.groupdict())

    def get_extra_info(self, name: str):
        if name == 'socket':
            return self.socket
        elif name == 'peername':
            return 'test'

    async def readline(self) -> bytes:
        where, data, wait, set = self._pop_expected(_Type.READLINE)
        if set:
            set.set()
        if wait:
            try:
                await asyncio.wait_for(wait.wait(), timeout=1.0)
            except asyncio.TimeoutError:
                assert False, '\nTimeout: 1.0s' + \
                              '\nWhere:   ' + where
        return data

    async def readexactly(self, size: int) -> bytes:
        where, data, wait, set = self._pop_expected(_Type.READEXACTLY)
        assert size == len(data), '\nExpected: ' + repr(len(data)) + \
                                  '\nGot:      ' + repr(size) + \
                                  '\nWhere:    ' + where
        if set:
            set.set()
        if wait:
            try:
                await asyncio.wait_for(wait.wait(), timeout=1.0)
            except asyncio.TimeoutError:
                assert False, '\nTimeout: 1.0s' + \
                              '\nWhere:   ' + where
        return data

    def write(self, data: bytes) -> None:
        where, expected, _, _ = self._pop_expected(_Type.WRITE)
        self._match_write(where, expected, data)

    async def drain(self) -> None:
        _, _, wait, set = self._pop_expected(_Type.DRAIN)
        if set:
            set.set()
        if wait:
            try:
                await asyncio.wait_for(wait.wait(), timeout=1.0)
            except asyncio.TimeoutError:
                assert False, '\nTimeout: 1.0s'

    def at_eof(self):
        return False

    def close(self) -> None:
        _, _, _, set = self._pop_expected(_Type.WRITE_CLOSE)
        assert 0 == len(self.queue), 'Items left on queue: ' + repr(self.queue)
        if set:
            set.set()
