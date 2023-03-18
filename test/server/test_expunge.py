
from .base import TestBase

from pymap.imap import IMAPServer


class TestExpunge(TestBase):

    async def test_expunge(self, imap_server: IMAPServer) -> None:
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_select(b'INBOX')
        transport.push_readline(
            b'store1 STORE * +FLAGS (\\Deleted)\r\n')
        transport.push_write(
            b'* 4 FETCH (FLAGS (\\Deleted \\Recent))\r\n'
            b'store1 OK STORE completed.\r\n')
        transport.push_readline(
            b'expunge1 EXPUNGE\r\n')
        transport.push_write(
            b'* 4 EXPUNGE\r\n'
            b'* 0 RECENT\r\n'
            b'expunge1 OK EXPUNGE completed.\r\n')
        transport.push_logout()
        await self.run(transport)

    async def test_expunge_uid(self, imap_server: IMAPServer) -> None:
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_select(b'INBOX')
        transport.push_readline(
            b'store1 UID STORE * +FLAGS (\\Deleted)\r\n')
        transport.push_write(
            b'* 4 FETCH (FLAGS (\\Deleted \\Recent) UID 104)\r\n'
            b'store1 OK UID STORE completed.\r\n')
        transport.push_readline(
            b'expunge1 UID EXPUNGE 101:103\r\n')
        transport.push_write(
            b'expunge1 OK UID EXPUNGE completed.\r\n')
        transport.push_readline(
            b'expunge1 UID EXPUNGE 101:*\r\n')
        transport.push_write(
            b'* 4 EXPUNGE\r\n'
            b'* 0 RECENT\r\n'
            b'expunge1 OK UID EXPUNGE completed.\r\n')
        transport.push_logout()
        await self.run(transport)

    async def test_concurrent_expunge_responses(
            self, imap_server: IMAPServer) -> None:
        transport = self.new_transport(imap_server)
        concurrent = self.new_transport(imap_server)
        event1, event2 = self.new_events(2)

        concurrent.push_login()
        concurrent.push_select(b'INBOX', 4, 1, set=event1)
        concurrent.push_readline(
            b'fetch1 FETCH 1:* (UID FLAGS)\r\n', wait=event2)
        concurrent.push_write(
            b'* 1 FETCH (UID 101 FLAGS (\\Seen))\r\n'
            b'* 2 FETCH (UID 102 FLAGS (\\Answered \\Seen))\r\n'
            b'* 3 FETCH (UID 103 FLAGS (\\Flagged))\r\n'
            b'* 4 FETCH (UID 104 FLAGS (\\Deleted \\Recent))\r\n'
            b'fetch1 OK [EXPUNGEISSUED] FETCH completed.\r\n')
        concurrent.push_readline(
            b'store2 STORE 1:* +FLAGS (\\Flagged)\r\n')
        concurrent.push_write(
            b'* 1 FETCH (FLAGS (\\Flagged \\Seen))\r\n'
            b'* 2 FETCH (FLAGS (\\Answered \\Flagged \\Seen))\r\n'
            b'* 3 FETCH (FLAGS (\\Flagged))\r\n'
            b'* 4 FETCH (FLAGS (\\Deleted \\Flagged \\Recent))\r\n'
            b'store2 OK [EXPUNGEISSUED] STORE completed.\r\n')
        concurrent.push_readline(
            b'search1 SEARCH ALL\r\n')
        concurrent.push_write(
            b'* SEARCH 1 2 3 4\r\n'
            b'search1 OK [EXPUNGEISSUED] SEARCH completed.\r\n')
        concurrent.push_readline(
            b'noop1 NOOP\r\n')
        concurrent.push_write(
            b'* 4 EXPUNGE\r\n'
            b'* 0 RECENT\r\n'
            b'noop1 OK NOOP completed.\r\n')
        concurrent.push_logout()

        transport.push_login()
        transport.push_select(b'INBOX', 4, 0, wait=event1)
        transport.push_readline(
            b'store1 STORE * +FLAGS (\\Deleted)\r\n')
        transport.push_write(
            b'* 4 FETCH (FLAGS (\\Deleted))\r\n'
            b'store1 OK STORE completed.\r\n')
        transport.push_readline(
            b'expunge1 EXPUNGE\r\n', set=event2)
        transport.push_write(
            b'* 4 EXPUNGE\r\n'
            b'expunge1 OK EXPUNGE completed.\r\n')
        transport.push_logout()

        await self.run(transport, concurrent)
