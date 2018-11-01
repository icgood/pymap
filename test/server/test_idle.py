
import pytest  # type: ignore

from .base import TestBase

pytestmark = pytest.mark.asyncio


class TestIdle(TestBase):

    async def test_idle(self):
        self.transport.push_login()
        self.transport.push_select(b'INBOX', 4, 1, 105, 4)
        self.transport.push_readline(
            b'idle1 IDLE\r\n')
        self.transport.push_write(
            b'+ Idling.\r\n')
        self.transport.push_readexactly(
            b'DONE')
        self.transport.push_readline(
            b'\r\n')
        self.transport.push_write(
            b'idle1 OK IDLE completed.\r\n')
        self.transport.push_logout()
        await self.run()

    async def test_idle_noselect(self):
        self.transport.push_login()
        self.transport.push_readline(
            b'idle1 IDLE\r\n')
        self.transport.push_write(
            b'idle1 BAD IDLE: Must select a mailbox first.\r\n')
        self.transport.push_logout()
        await self.run()

    async def test_concurrent_idle_append(self):
        concurrent = self.new_transport()
        event1, event2 = self.new_events(2)

        concurrent.push_login()
        concurrent.push_select(b'INBOX', 4, 1, 105, 4)
        concurrent.push_readline(
            b'idle1 IDLE\r\n')
        concurrent.push_write(
            b'+ Idling.\r\n', set=event1)
        concurrent.push_readexactly(
            b'DONE')
        concurrent.push_readline(
            b'\r\n', wait=event2)
        concurrent.push_write(
            b'* 5 EXISTS\r\n')
        concurrent.push_write(
            b'* 2 RECENT\r\n')
        concurrent.push_write(
            b'* 5 FETCH (FLAGS (\\Recent \\Seen))\r\n')
        concurrent.push_write(
            b'idle1 OK IDLE completed.\r\n')
        concurrent.push_logout()

        self.transport.push_login()
        self.transport.push_readline(
            b'append1 APPEND INBOX (\\Seen) {9}\r\n', wait=event1)
        self.transport.push_write(
            b'+ Literal string\r\n')
        self.transport.push_readexactly(
            b'testing\r\n')
        self.transport.push_readline(
            b'\r\n')
        self.transport.push_write(
            b'append1 OK [APPENDUID ', None, b' 105] APPEND completed.\r\n',
            set=event2)
        self.transport.push_logout()

        await self.run(concurrent)

    async def test_concurrent_idle_expunge(self):
        concurrent = self.new_transport()
        event1, event2 = self.new_events(2)

        concurrent.push_login()
        concurrent.push_select(b'INBOX', 4, 1, 105, 4)
        concurrent.push_readline(
            b'idle1 IDLE\r\n')
        concurrent.push_write(
            b'+ Idling.\r\n', set=event1)
        concurrent.push_readexactly(
            b'DONE')
        concurrent.push_readline(
            b'\r\n', wait=event2)
        concurrent.push_write(
            b'* 1 EXPUNGE\r\n')
        concurrent.push_write(
            b'idle1 OK IDLE completed.\r\n')
        concurrent.push_logout()

        self.transport.push_login()
        self.transport.push_select(b'INBOX', 4, 0, 105, 4, wait=event1)
        self.transport.push_readline(
            b'store1 STORE 1 +FLAGS.SILENT (\\Deleted)\r\n')
        self.transport.push_write(
            b'store1 OK STORE completed.\r\n')
        self.transport.push_readline(
            b'close1 CLOSE\r\n')
        self.transport.push_write(
            b'close1 OK CLOSE completed.\r\n', set=event2)
        self.transport.push_logout()

        await self.run(concurrent)
