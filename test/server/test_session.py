
import pytest

from .base import TestBase

pytestmark = pytest.mark.asyncio


class TestSession(TestBase):

    async def test_login_logout(self):
        self.login()
        self.logout()
        await self.run()

    async def test_select(self):
        self.login()
        self.select(b'INBOX', 4, 1, 104, 4)
        self.logout()
        await self.run()

    async def test_select_clears_recent(self):
        self.login()
        self.select(b'INBOX', 4, 1, 104, 4)
        self.select(b'INBOX', 4, 0, 104, 4)
        self.logout()
        await self.run()

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
        self.logout()
        await self.run()
