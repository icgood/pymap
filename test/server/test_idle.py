
from .base import TestBase

from pymap.imap import IMAPServer


class TestIdle(TestBase):

    async def test_idle(self, imap_server: IMAPServer) -> None:
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_select(b'INBOX', 4, 1, 105)
        transport.push_readline(
            b'idle1 IDLE\r\n')
        transport.push_write(
            b'+ Idling.\r\n')
        transport.push_readexactly(b'')
        transport.push_readline(
            b'DONE\r\n')
        transport.push_write(
            b'idle1 OK IDLE completed.\r\n')
        transport.push_logout()
        await self.run(transport)

    async def test_idle_invalid(self, imap_server: IMAPServer) -> None:
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_select(b'INBOX', 4, 1, 105)
        transport.push_readline(
            b'idle1 IDLE\r\n')
        transport.push_write(
            b'+ Idling.\r\n')
        transport.push_readexactly(b'')
        transport.push_readline(
            b'WHAT\r\n')
        transport.push_write(
            b'idle1 BAD Expected "DONE".\r\n')
        transport.push_logout()
        await self.run(transport)

    async def test_idle_noselect(self, imap_server: IMAPServer) -> None:
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_readline(
            b'idle1 IDLE\r\n')
        transport.push_write(
            b'idle1 BAD IDLE: Must select a mailbox first.\r\n')
        transport.push_logout()
        await self.run(transport)

    async def test_concurrent_idle_append(self, imap_server: IMAPServer) \
            -> None:
        transport = self.new_transport(imap_server)
        concurrent = self.new_transport(imap_server)
        event1, event2, event3 = self.new_events(3)

        concurrent.push_login()
        concurrent.push_select(b'INBOX', 4, 1, 105)
        concurrent.push_readline(
            b'idle1 IDLE\r\n')
        concurrent.push_write(
            b'+ Idling.\r\n')
        concurrent.push_readexactly(b'', set=event1, wait=event3)
        concurrent.push_write(
            b'* 5 EXISTS\r\n')
        concurrent.push_write(
            b'* 2 RECENT\r\n')
        concurrent.push_write(
            b'* 5 FETCH (FLAGS (\\Recent \\Seen))\r\n', set=event3)
        concurrent.push_readline(
            b'DONE\r\n')
        concurrent.push_write(
            b'idle1 OK IDLE completed.\r\n')
        concurrent.push_logout()

        transport.push_login()
        transport.push_readline(
            b'append1 APPEND INBOX (\\Seen) {9}\r\n', wait=event1)
        transport.push_write(
            b'+ Literal string\r\n')
        transport.push_readexactly(
            b'testing\r\n')
        transport.push_readline(
            b'\r\n')
        transport.push_write(
            b'append1 OK [APPENDUID ', None, b' 105] APPEND completed.\r\n',
            set=event2)
        transport.push_logout()

        await self.run(transport, concurrent)

    async def test_concurrent_idle_expunge(self, imap_server: IMAPServer) \
            -> None:
        transport = self.new_transport(imap_server)
        concurrent = self.new_transport(imap_server)
        event1, event2, event3 = self.new_events(3)

        concurrent.push_login()
        concurrent.push_select(b'INBOX', 4, 1, 105)
        concurrent.push_readline(
            b'idle1 IDLE\r\n')
        concurrent.push_write(
            b'+ Idling.\r\n')
        concurrent.push_readexactly(b'', set=event1, wait=event3)
        concurrent.push_write(
            b'* 1 EXPUNGE\r\n', set=event3)
        concurrent.push_readline(
            b'DONE\r\n', wait=event2)
        concurrent.push_write(
            b'idle1 OK IDLE completed.\r\n')
        concurrent.push_logout()

        transport.push_login()
        transport.push_select(b'INBOX', 4, 0, 105, wait=event1)
        transport.push_readline(
            b'store1 STORE 1 +FLAGS.SILENT (\\Deleted)\r\n')
        transport.push_write(
            b'store1 OK STORE completed.\r\n')
        transport.push_readline(
            b'close1 CLOSE\r\n')
        transport.push_write(
            b'close1 OK CLOSE completed.\r\n', set=event2)
        transport.push_logout()

        await self.run(transport, concurrent)
