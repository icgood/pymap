
import pytest  # type: ignore

from .base import TestBase

pytestmark = pytest.mark.asyncio


class TestReadOnly(TestBase):

    async def test_select(self):
        self.transport.push_login()
        self.transport.push_select(b'Trash', 1, 1, readonly=True)
        self.transport.push_select(b'Trash', 1, 1, readonly=True)
        self.transport.push_logout()
        await self.run()

    async def test_examine(self):
        self.transport.push_login()
        self.transport.push_select(b'INBOX', 4, 1, examine=True)
        self.transport.push_select(b'INBOX', 4, 1, examine=True)
        self.transport.push_logout()
        await self.run()

    async def test_append(self):
        message = b'test message\r\n'
        self.transport.push_login()
        self.transport.push_readline(
            b'append1 APPEND Trash (\\Seen) {%i}\r\n' % len(message))
        self.transport.push_write(
            b'+ Literal string\r\n')
        self.transport.push_readexactly(message)
        self.transport.push_readline(
            b'\r\n')
        self.transport.push_write(
            b'append1 NO [READ-ONLY] Mailbox is read-only.\r\n')
        self.transport.push_select(b'Trash', 1, readonly=True)
        self.transport.push_logout()
        await self.run()

    async def test_copy(self):
        self.transport.push_login()
        self.transport.push_select(b'INBOX')
        self.transport.push_readline(
            b'copy1 COPY 1 Trash\r\n')
        self.transport.push_write(
            b'copy1 NO [READ-ONLY] Mailbox is read-only.\r\n')
        self.transport.push_select(b'Trash', 1, readonly=True)
        self.transport.push_logout()
        await self.run()

    async def test_expunge(self):
        self.transport.push_login()
        self.transport.push_select(b'Trash', 1, readonly=True)
        self.transport.push_readline(
            b'expunge1 EXPUNGE\r\n')
        self.transport.push_write(
            b'expunge1 NO [READ-ONLY] Mailbox is read-only.\r\n')
        self.transport.push_select(b'Trash', 1, readonly=True)
        self.transport.push_logout()
        await self.run()

    async def test_store(self):
        self.transport.push_login()
        self.transport.push_select(b'Trash', 1, readonly=True)
        self.transport.push_readline(
            b'store1 STORE 1 +FlAGS (\\Seen)\r\n')
        self.transport.push_write(
            b'store1 NO [READ-ONLY] Mailbox is read-only.\r\n')
        self.transport.push_logout()
        await self.run()

    async def test_fetch_not_seen(self):
        self.transport.push_login()
        self.transport.push_select(b'Trash', 1, readonly=True)
        self.transport.push_readline(
            b'fetch1 FETCH 1 (FLAGS)\r\n')
        self.transport.push_write(
            b'* 1 FETCH (FLAGS (\\Deleted))\r\n'
            b'fetch1 OK FETCH completed.\r\n')
        self.transport.push_readline(
            b'fetch2 FETCH 1 (RFC822.TEXT FLAGS)\r\n')
        self.transport.push_write(
            b'* 1 FETCH (RFC822.TEXT {53}\r\n'
            b'It just works. Only five easy payments of $19.99.\r\n\r\n'
            b' FLAGS (\\Deleted))\r\n'
            b'fetch2 OK FETCH completed.\r\n')
        self.transport.push_logout()
        await self.run()
