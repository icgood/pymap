
import asyncio
import enum
import inspect
import re
import socket
import traceback
from collections import deque
from itertools import zip_longest
from typing import overload, Any, Literal, NoReturn

from pymap.concurrent import Event
from pymap.imap import IMAPServer
from pymap.sieve.manage import ManageSieveServer

__all__ = ['MockTransport']


class _Type(enum.Enum):
    READLINE = "reader.readline()"
    READEXACTLY = "reader.readexactly()"
    DRAIN = "writer.drain()"
    READ_EOF = "reader.at_eof()"


class _Socket:

    def __init__(self, fd: int) -> None:
        self.fd = fd
        self.family = socket.AF_INET

    def fileno(self) -> int:
        return self.fd


_WriteDataTuple = tuple['_WriteDataPart', ...]
_WriteDataPart = bytes | int | _WriteDataTuple | None
_WriteData = bytes | int | _WriteDataTuple
_ReadLineOp = tuple[Literal[_Type.READLINE], str, bytes,
                    Event | None, Event | None]
_ReadExactlyOp = tuple[Literal[_Type.READEXACTLY], str, bytes,
                       Event | None, Event | None]
_DrainOp = tuple[Literal[_Type.DRAIN], str, _WriteDataTuple,
                 Event | None, Event | None]
_ReadEofOp = tuple[Literal[_Type.READ_EOF], str, None,
                   Event | None, Event | None]
_Operation = _ReadLineOp | _ReadExactlyOp | _DrainOp | _ReadEofOp
_Server = IMAPServer | ManageSieveServer


class MockTransport:

    def __init__(self, server: _Server, matches: dict[str, bytes], fd) -> None:
        self.server = server
        self.queue: deque[_Operation] = deque()
        self.matches = matches
        self.socket = _Socket(fd)
        self._write_batch: list[bytes] = []
        self._select_count = 0

    @classmethod
    def _caller(cls, frame) -> str:
        frame = frame.f_back if frame else None
        fields = inspect.getframeinfo(frame) if frame else ('?', '?')
        return '{0}:{1!s}'.format(fields[0], fields[1])

    @classmethod
    def _fail(cls, msg: str) -> NoReturn:
        raise AssertionError(msg)

    def push_readline(self, data: bytes, wait: Event | None = None,
                      set: Event | None = None) -> None:
        where = self._caller(inspect.currentframe())
        self.queue.append((_Type.READLINE, where, data, wait, set))

    def push_readexactly(self, data: bytes, wait: Event | None = None,
                         set: Event | None = None) -> None:
        where = self._caller(inspect.currentframe())
        self.queue.append((_Type.READEXACTLY, where, data, wait, set))

    def push_write(self, *data: _WriteDataPart, wait: Event | None = None,
                   set: Event | None = None) -> None:
        where = self._caller(inspect.currentframe())
        self.queue.append((_Type.DRAIN, where, data, wait, set))

    def push_read_eof(self, wait: Event | None = None,
                      set: Event | None = None) -> None:
        where = self._caller(inspect.currentframe())
        self.queue.append((_Type.READ_EOF, where, None, wait, set))

    def push_login(self, password: bytes = b'testpass',
                   wait: Event | None = None,
                   set: Event | None = None) -> None:
        self.push_write(
            b'* OK [CAPABILITY IMAP4rev1',
            (br'(?:\s+[a-zA-Z0-9=+-]+)*', ),
            b'] Server ready ',
            (br'\S+', ), b'\r\n', wait=wait)
        self.push_readline(
            b'login1 LOGIN testuser ' + password + b'\r\n')
        self.push_write(
            b'login1 OK [CAPABILITY IMAP4rev1',
            (br'(?:\s+[a-zA-Z0-9=+-]+)*', ),
            b'] Authentication successful.\r\n', set=set)

    def push_logout(self, wait: Event | None = None, set: Event | None = None):
        self.push_readline(
            b'logout1 LOGOUT\r\n', wait=wait)
        self.push_write(
            b'* BYE Logging out.\r\n'
            b'logout1 OK Logout successful.\r\n', set=set)

    def push_select(self, mailbox: bytes,
                    exists: _WriteData | None = None,
                    recent: _WriteData | None = None,
                    uidnext: _WriteData | None = None,
                    unseen: _WriteData | Literal[False] | None = None,
                    readonly: bool = False, examine: bool = False,
                    wait: Event | None = None,
                    post_wait: Event | None = None,
                    set: Event | None = None) -> None:
        n = self._select_count = self._select_count + 1
        if unseen is False:
            unseen_line: _WriteData = (None, b'')
        elif unseen is None:
            unseen_line = (None, b'* OK [UNSEEN ', (br'\d+',),
                           b'] First unseen message.\r\n')
        else:
            unseen_line = (None, b'* OK [UNSEEN ', unseen,
                           b'] First unseen message.\r\n')
        if exists is None:
            exists = (br'\d+', )
        if recent is None:
            recent = (br'\d+', )
        if uidnext is None:
            uidnext = (br'\d+', )
        if readonly or examine:
            ok_code = b'READ-ONLY'
            permflags_line = b'* OK [PERMANENTFLAGS ()] Read-only mailbox.\r\n'
        else:
            ok_code = b'READ-WRITE'
            permflags_line = b'* OK [PERMANENTFLAGS (' \
                             b'\\Answered \\Deleted \\Draft \\Flagged ' \
                             b'\\Seen)] Flags permitted.\r\n'
        if examine:
            tag = b'examine%i' % (n, )
            cmd = b'EXAMINE'
        else:
            tag = b'select%i' % (n, )
            cmd = b'SELECT'
        self.push_readline(
            tag + b' ' + cmd + b' ' + mailbox + b'\r\n', wait=wait)
        self.push_write(
            permflags_line,
            b'* FLAGS (\\Answered \\Deleted \\Draft '
            b'\\Flagged \\Recent \\Seen)\r\n'
            b'* ', exists, b' EXISTS\r\n'
            b'* ', recent, b' RECENT\r\n'
            b'* OK [UIDNEXT ', uidnext, b'] Predicted next UID.\r\n'
            b'* OK [UIDVALIDITY ', (br'\d+', ), b'] UIDs valid.\r\n',
            unseen_line,
            b'* OK [MAILBOXID (', (br'F[a-f0-9]+', b'mbxid%i' % (n, )), b')] '
            b'Object ID.\r\n',
            tag, b' OK [', ok_code, b'] Selected mailbox.\r\n',
            wait=post_wait, set=set)

    @overload
    def _pop_expected(self, got: Literal[_Type.READLINE]) -> _ReadLineOp:
        ...

    @overload
    def _pop_expected(self, got: Literal[_Type.READEXACTLY]) -> _ReadExactlyOp:
        ...

    @overload
    def _pop_expected(self, got: Literal[_Type.DRAIN]) -> _DrainOp:
        ...

    @overload
    def _pop_expected(self, got: Literal[_Type.READ_EOF]) -> _ReadEofOp:
        ...

    def _pop_expected(self, got: _Type) -> _Operation:
        try:
            try:
                type_, where, data, wait, set = self.queue.popleft()
            except IndexError as exc:
                raise AssertionError('\nExpected: <end>'
                                     '\nGot:      ' + got.value) from exc
            if type_ != got:
                raise AssertionError('\nExpected: ' + type_.value +
                                     '\nGot:      ' + got.value +
                                     '\nWhere:    ' + where)
        except AssertionError:
            traceback.print_exc()
            raise
        return got, where, data, wait, set  # type: ignore

    def _match_write_expected(self, expected: _WriteDataTuple,
                              re_parts: list[bytes]) -> None:
        for part in expected:
            if part is None:
                re_parts.append(br'.*?')
            elif isinstance(part, bytes):
                re_parts.append(re.escape(part))
            elif isinstance(part, int):
                re_parts.append(b'%i' % part)
            else:
                if len(part) == 1 or part[1] is None:
                    assert isinstance(part[0], bytes)
                    re_parts.append(part[0])
                elif part[0] is None:
                    self._match_write_expected(part[1:], re_parts)
                else:
                    regex, name = part
                    assert isinstance(regex, bytes)
                    assert isinstance(name, bytes)
                    re_parts.append(br'(?P<' + name + br'>' + regex + br')')

    def _match_write_msg(self, expected: _WriteData, data: bytes,
                         full_regex: bytes, where: str) -> str:
        parts = ['',
                 'Expected: ' + repr(expected),
                 'Got:      ' + repr((data, )),
                 'Where:    ' + where,
                 '---------------------------------------------------']
        raw_regex = str(full_regex.replace(b'\r', b''), 'utf-8').splitlines()
        raw_data = str(data, 'utf-8').splitlines()
        for regex_line, data_line in zip_longest(raw_regex, raw_data):
            if regex_line:
                parts.append('regex: ' + regex_line.lstrip('^'))
            else:
                parts.append('regex: ')
            if data_line:
                parts.append('data:  ' + re.escape(data_line + '\\'))
            else:
                parts.append('data:  ')
            parts.append('')
        return '\n'.join(parts)

    def _match_write(self, where: str, expected: _WriteDataTuple,
                     data: bytes) -> None:
        re_parts: list[bytes] = []
        self._match_write_expected(expected, re_parts)
        full_regex = b'^' + b''.join(re_parts) + b'$'
        match = re.search(full_regex, data)
        if not match:
            raise AssertionError(
                self._match_write_msg(expected, data, full_regex, where))
        self.matches.update(match.groupdict())

    def get_extra_info(self, name: str, default: Any = None) -> Any:
        if name == 'socket':
            return self.socket
        elif name == 'peername':
            return ('1.2.3.4', 1234)
        elif name == 'sockname':
            return ('5.6.7.8', 5678)

    async def readline(self) -> bytes:
        _, where, data, wait, set = self._pop_expected(_Type.READLINE)
        if set:
            set.set()
        if wait:
            try:
                await asyncio.wait_for(wait.wait(), timeout=1.0)
            except asyncio.TimeoutError:
                self._fail('\nTimeout: 1.0s' +
                           '\nWhere:   ' + where)
        return data % {key.encode('ascii'): val
                       for key, val in self.matches.items()}

    async def readexactly(self, size: int) -> bytes:
        _, where, data, wait, set = self._pop_expected(_Type.READEXACTLY)
        if size != len(data):
            raise AssertionError('\nExpected: ' + repr(len(data)) +
                                 '\nGot:      ' + repr(size) +
                                 '\nWhere:    ' + where)
        if set:
            set.set()
        if wait:
            try:
                await asyncio.wait_for(wait.wait(), timeout=1.0)
            except asyncio.TimeoutError:
                self._fail('\nTimeout: 1.0s' +
                           '\nWhere:   ' + where)
        return data

    def write(self, data: bytes) -> None:
        self._write_batch.append(data)

    async def drain(self) -> None:
        _, where, expected, wait, set = self._pop_expected(_Type.DRAIN)
        data = b''.join(self._write_batch)
        self._write_batch = []
        self._match_write(where, expected, data)
        if set:
            set.set()
        if wait:
            try:
                await asyncio.wait_for(wait.wait(), timeout=1.0)
            except asyncio.TimeoutError:
                self._fail('\nTimeout: 1.0s')

    def at_eof(self) -> Literal[False]:
        return False

    def close(self) -> None:
        pass
