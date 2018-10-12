
import pytest  # type: ignore

from .base import TestBase

pytestmark = pytest.mark.asyncio


class TestExpunge(TestBase):

    async def test_expunge(self):
        self.transport.push_login()
        self.transport.push_select(b'INBOX')
        self.transport.push_readline(
            b'store1 STORE * +FlAGS (\\Deleted)\r\n')
        self.transport.push_write(
            b'* 4 FETCH (FLAGS (\\Deleted \\Recent))\r\n'
            b'store1 OK STORE completed.\r\n')
        self.transport.push_readline(
            b'expunge1 EXPUNGE\r\n')
        self.transport.push_write(
            b'* 3 EXISTS\r\n'
            b'* 0 RECENT\r\n'
            b'* 4 EXPUNGE\r\n'
            b'expunge1 OK EXPUNGE completed.\r\n')
        self.transport.push_logout()
        await self.run()

    async def test_concurrent_expunge_responses(self):
        concurrent = self.new_transport()
        event1, event2 = self.new_events(2)

        concurrent.push_login()
        concurrent.push_select(b'INBOX', 4, 1, set=event1)
        concurrent.push_readline(
            b'noop1 NOOP\r\n', wait=event2)
        concurrent.push_write(
            b'* 3 EXISTS\r\n'
            b'* 0 RECENT\r\n'
            b'* 4 EXPUNGE\r\n'
            b'noop1 OK NOOP completed.\r\n')
        concurrent.push_logout()

        self.transport.push_login()
        self.transport.push_select(b'INBOX', 4, 0, wait=event1)
        self.transport.push_readline(
            b'store1 STORE * +FlAGS (\\Deleted)\r\n')
        self.transport.push_write(
            b'* 4 FETCH (FLAGS (\\Deleted))\r\n'
            b'store1 OK STORE completed.\r\n')
        self.transport.push_readline(
            b'expunge1 EXPUNGE\r\n', set=event2)
        self.transport.push_write(
            b'* 3 EXISTS\r\n'
            b'* 4 EXPUNGE\r\n'
            b'expunge1 OK EXPUNGE completed.\r\n')
        self.transport.push_logout()

        await self.run(concurrent)
