
from .base import TestBase

from pymap.imap import IMAPServer


class TestReadOnly(TestBase):

    async def test_select(self, imap_server: IMAPServer) -> None:
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_select(b'Trash', 1, 1, readonly=True)
        transport.push_select(b'Trash', 1, 1, readonly=True)
        transport.push_logout()
        await self.run(transport)

    async def test_examine(self, imap_server: IMAPServer) -> None:
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_select(b'INBOX', 4, 1, examine=True)
        transport.push_select(b'INBOX', 4, 1, examine=True)
        transport.push_logout()
        await self.run(transport)

    async def test_append(self, imap_server: IMAPServer) -> None:
        transport = self.new_transport(imap_server)
        message = b'test message\r\n'
        transport.push_login()
        transport.push_readline(
            b'append1 APPEND Trash (\\Seen) {%i}\r\n' % len(message))
        transport.push_write(
            b'+ Literal string\r\n')
        transport.push_readexactly(message)
        transport.push_readline(
            b'\r\n')
        transport.push_write(
            b'append1 NO [READ-ONLY] Mailbox is read-only.\r\n')
        transport.push_select(b'Trash', 1, readonly=True)
        transport.push_logout()
        await self.run(transport)

    async def test_copy(self, imap_server: IMAPServer) -> None:
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_select(b'INBOX')
        transport.push_readline(
            b'copy1 COPY 1 Trash\r\n')
        transport.push_write(
            b'copy1 NO [READ-ONLY] Mailbox is read-only.\r\n')
        transport.push_select(b'Trash', 1, readonly=True)
        transport.push_logout()
        await self.run(transport)

    async def test_expunge(self, imap_server: IMAPServer) -> None:
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_select(b'Trash', 1, readonly=True)
        transport.push_readline(
            b'expunge1 EXPUNGE\r\n')
        transport.push_write(
            b'expunge1 NO [READ-ONLY] Mailbox is read-only.\r\n')
        transport.push_select(b'Trash', 1, readonly=True)
        transport.push_logout()
        await self.run(transport)

    async def test_store(self, imap_server: IMAPServer) -> None:
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_select(b'Trash', 1, readonly=True)
        transport.push_readline(
            b'store1 STORE 1 +FlAGS (\\Seen)\r\n')
        transport.push_write(
            b'store1 NO [READ-ONLY] Mailbox is read-only.\r\n')
        transport.push_logout()
        await self.run(transport)

    async def test_fetch_not_seen(self, imap_server: IMAPServer) -> None:
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_select(b'Trash', 1, readonly=True)
        transport.push_readline(
            b'fetch1 FETCH 1 (FLAGS)\r\n')
        transport.push_write(
            b'* 1 FETCH (FLAGS (\\Deleted))\r\n'
            b'fetch1 OK FETCH completed.\r\n')
        transport.push_readline(
            b'fetch2 FETCH 1 (RFC822.TEXT FLAGS)\r\n')
        transport.push_write(
            b'* 1 FETCH (RFC822.TEXT {53}\r\n'
            b'It just works. Only five easy payments of $19.99.\r\n\r\n'
            b' FLAGS (\\Deleted))\r\n'
            b'fetch2 OK FETCH completed.\r\n')
        transport.push_logout()
        await self.run(transport)
