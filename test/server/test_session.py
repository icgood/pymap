
import pytest

from .base import TestBase

pytestmark = pytest.mark.asyncio


class TestSession(TestBase):

    async def test_login_logout(self):
        self.transport.push_login()
        self.transport.push_logout()
        await self.run()

    async def test_select(self):
        self.transport.push_login()
        self.transport.push_select(b'INBOX', 4, 1, 104, 4)
        self.transport.push_logout()
        await self.run()

    async def test_select_clears_recent(self):
        self.transport.push_login()
        self.transport.push_select(b'INBOX', 4, 1, 104, 4)
        self.transport.push_select(b'INBOX', 4, 0, 104, 4)
        self.transport.push_logout()
        await self.run()

    async def test_concurrent_select_clears_recent(self):
        concurrent = self.new_transport()
        event1, event2 = self.new_events(2)

        concurrent.push_login()
        concurrent.push_readline(
            b'status1 STATUS INBOX (MESSAGES RECENT)\r\n')
        concurrent.push_write(
            b'* STATUS INBOX (MESSAGES 4 RECENT 1)\r\n'
            b'status1 OK STATUS completed.\r\n', set=event1)
        concurrent.push_select(b'INBOX', 4, 0, 104, 4, wait=event2)
        concurrent.push_logout()

        self.transport.push_login()
        self.transport.push_select(b'INBOX', 4, 1, 104, 4,
                                   wait=event1, set=event2)
        self.transport.push_logout()

        await self.run(concurrent)

    async def test_auth_plain(self):
        self.transport.push_write(
            b'* OK [CAPABILITY IMAP4rev1 AUTH=PLAIN] Server ready ',
            (br'\S+',), b'\r\n')
        self.transport.push_readline(
            b'auth1 AUTHENTICATE PLAIN\r\n')
        self.transport.push_write(
            b'+ \r\n')
        self.transport.push_readexactly(b'')
        self.transport.push_readline(
            b'AGRlbW91c2VyAGRlbW9wYXNz\r\n')
        self.transport.push_write(
            b'auth1 OK Authentication successful.\r\n')
        self.transport.push_logout()
        await self.run()
