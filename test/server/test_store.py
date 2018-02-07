
import pytest

from .base import TestBase

pytestmark = pytest.mark.asyncio


class TestStore(TestBase):

    async def test_store(self):
        self.login()
        self.select(b'INBOX', 4, 1, 104, 4)
        self.transport.push_readline(
            b'store1 STORE * +FlAGS (\\Seen)\r\n')
        self.transport.push_write(
            b'* 4 FETCH (FLAGS (\\Recent \\Seen))\r\n'
            b'store1 OK STORE completed.\r\n')
        self.logout()
        await self.run()

    async def test_uid_store(self):
        self.login()
        self.select(b'INBOX', 4, 1, 104, 4)
        self.transport.push_readline(
            b'store1 UID STORE * +FlAGS (\\Seen)\r\n')
        self.transport.push_write(
            b'* 4 FETCH (FLAGS (\\Recent \\Seen) UID 103)\r\n'
            b'store1 OK STORE completed.\r\n')
        self.logout()
        await self.run()

    async def test_store_add_recent(self):
        self.login()
        self.select(b'INBOX', 4, 1, 104, 4)
        self.transport.push_readline(
            b'store1 STORE 1 +FlAGS (\\Recent)\r\n')
        self.transport.push_write(
            b'* 1 FETCH (FLAGS (\\Seen))\r\n'
            b'store1 OK STORE completed.\r\n')
        self.logout()
        await self.run()

    async def test_store_remove_recent(self):
        self.login()
        self.select(b'INBOX', 4, 1, 104, 4)
        self.transport.push_readline(
            b'store1 STORE * -FlAGS (\\Recent)\r\n')
        self.transport.push_write(
            b'* 4 FETCH (FLAGS (\\Recent))\r\n'
            b'store1 OK STORE completed.\r\n')
        self.logout()
        await self.run()

    async def test_store_invalid(self):
        self.login()
        self.select(b'INBOX', 4, 1, 104, 4)
        self.transport.push_readline(
            b'store1 STORE * +FlAGS (\\Invalid)\r\n')
        self.transport.push_write(
            b'* 4 FETCH (FLAGS (\\Recent))\r\n'
            b'store1 OK STORE completed.\r\n')
        self.logout()
        await self.run()