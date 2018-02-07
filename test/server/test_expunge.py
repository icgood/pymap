
import pytest

from .base import TestBase

pytestmark = pytest.mark.asyncio


class TestServer(TestBase):

    async def test_expunge(self):
        self.login()
        self.select(b'INBOX', 4, 1, 104, 4)
        self.transport.push_readline(
            b'store1 STORE * +FlAGS (\\Deleted)\r\n')
        self.transport.push_write(
            b'* 4 FETCH (FLAGS (\\Deleted \\Recent))\r\n'
            b'store1 OK STORE completed.\r\n')
        self.transport.push_readline(
            b'expunge1 EXPUNGE\r\n')
        self.transport.push_write(
            b'* 4 EXPUNGE\r\n'
            b'* 3 EXISTS\r\n'
            b'* 0 RECENT\r\n'
            b'expunge1 OK EXPUNGE completed.\r\n')
        self.logout()
        await self.run()

