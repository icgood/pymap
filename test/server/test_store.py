
from .base import TestBase

from pymap.imap import IMAPServer


class TestStore(TestBase):

    async def test_store(self, imap_server: IMAPServer) -> None:
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_select(b'INBOX')
        transport.push_readline(
            b'store1 STORE * +FLAGS (\\Seen)\r\n')
        transport.push_write(
            b'* 4 FETCH (FLAGS (\\Recent \\Seen))\r\n'
            b'store1 OK STORE completed.\r\n')
        transport.push_logout()
        await self.run(transport)

    async def test_store_silent(self, imap_server: IMAPServer) -> None:
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_select(b'INBOX')
        transport.push_readline(
            b'store1 STORE * +FLAGS.SILENT (\\Seen)\r\n')
        transport.push_write(
            b'store1 OK STORE completed.\r\n')
        transport.push_logout()
        await self.run(transport)

    async def test_uid_store(self, imap_server: IMAPServer) -> None:
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_select(b'INBOX')
        transport.push_readline(
            b'store1 UID STORE * +FLAGS (\\Seen)\r\n')
        transport.push_write(
            b'* 4 FETCH (FLAGS (\\Recent \\Seen) UID 104)\r\n'
            b'store1 OK UID STORE completed.\r\n')
        transport.push_logout()
        await self.run(transport)

    async def test_store_add_recent(self, imap_server: IMAPServer) -> None:
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_select(b'INBOX')
        transport.push_readline(
            b'store1 STORE 1 +FLAGS (\\Recent)\r\n')
        transport.push_write(
            b'* 1 FETCH (FLAGS (\\Seen))\r\n'
            b'store1 OK STORE completed.\r\n')
        transport.push_logout()
        await self.run(transport)

    async def test_store_remove_recent(self, imap_server: IMAPServer) -> None:
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_select(b'INBOX')
        transport.push_readline(
            b'store1 STORE * -FLAGS (\\Recent)\r\n')
        transport.push_write(
            b'* 4 FETCH (FLAGS (\\Recent))\r\n'
            b'store1 OK STORE completed.\r\n')
        transport.push_logout()
        await self.run(transport)

    async def test_store_set_non_recent(self, imap_server: IMAPServer) -> None:
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_select(b'INBOX')
        transport.push_readline(
            b'store1 STORE * FLAGS ()\r\n')
        transport.push_write(
            b'* 4 FETCH (FLAGS (\\Recent))\r\n'
            b'store1 OK STORE completed.\r\n')
        transport.push_logout()
        await self.run(transport)

    async def test_store_invalid(self, imap_server: IMAPServer) -> None:
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_select(b'INBOX', 4, 1)
        transport.push_readline(
            b'store1 STORE * +FLAGS (\\Invalid)\r\n')
        transport.push_write(
            b'* 4 FETCH (FLAGS (\\Recent))\r\n'
            b'store1 OK STORE completed.\r\n')
        transport.push_logout()
        await self.run(transport)
