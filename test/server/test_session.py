
import base64

from .base import TestBase

from pymap.imap import IMAPServer


class TestSession(TestBase):

    async def test_login_logout(self, imap_server: IMAPServer) -> None:
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_logout()
        await self.run(transport)

    async def test_select(self, imap_server: IMAPServer) -> None:
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_select(b'INBOX', 4, 1, 105, 3)
        transport.push_logout()
        await self.run(transport)

    async def test_select_clears_recent(self, imap_server: IMAPServer) -> None:
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_select(b'INBOX', 4, 1, 105, 3)
        transport.push_select(b'INBOX', 4, 0, 105, 3)
        transport.push_logout()
        await self.run(transport)

    async def test_concurrent_select_clears_recent(
            self, imap_server: IMAPServer) -> None:
        transport = self.new_transport(imap_server)
        concurrent = self.new_transport(imap_server)
        event1, event2 = self.new_events(2)

        concurrent.push_login()
        concurrent.push_readline(
            b'status1 STATUS INBOX (MESSAGES RECENT)\r\n')
        concurrent.push_write(
            b'* STATUS INBOX (MESSAGES 4 RECENT 1)\r\n'
            b'status1 OK STATUS completed.\r\n', set=event1)
        concurrent.push_select(b'INBOX', 4, 0, 105, 3, wait=event2)
        concurrent.push_logout()

        transport.push_login()
        transport.push_select(b'INBOX', 4, 1, 105, 3, wait=event1, set=event2)
        transport.push_logout()

        await self.run(transport, concurrent)

    async def test_auth_plain(self, imap_server: IMAPServer) -> None:
        transport = self.new_transport(imap_server)
        transport.push_write(
            b'* OK [CAPABILITY IMAP4rev1',
            (br'(?:\s+[a-zA-Z0-9=+-]+)*', ),
            b' AUTH=PLAIN',
            (br'(?:\s+[a-zA-Z0-9=+-]+)*',),
            b'] Server ready ',
            (br'\S+',), b'\r\n')
        transport.push_readline(
            b'auth1 AUTHENTICATE PLAIN\r\n')
        transport.push_write(
            b'+ \r\n')
        transport.push_readexactly(b'')
        transport.push_readline(
            base64.b64encode(b'\x00testuser\x00testpass') + b'\r\n')
        transport.push_write(
            b'auth1 OK [CAPABILITY IMAP4rev1',
            (br'(?:\s+[a-zA-Z0-9=+-]+)*', ),
            b'] Authentication successful.\r\n')
        transport.push_logout()
        await self.run(transport)
