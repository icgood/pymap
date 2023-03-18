
from .base import TestBase

from pymap.imap import IMAPServer


class TestCopy(TestBase):

    async def test_copy(self, imap_server: IMAPServer) -> None:
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_select(b'INBOX')
        transport.push_readline(
            b'copy1 COPY 1:* Sent\r\n')
        transport.push_write(
            b'copy1 OK [COPYUID ', (br'\d+', ), b' 101:104 103:106]'
            b' COPY completed.\r\n')
        transport.push_select(b'Sent', 6, 4)
        transport.push_logout()
        await self.run(transport)

    async def test_uid_copy(self, imap_server: IMAPServer) -> None:
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_select(b'INBOX')
        transport.push_readline(
            b'copy1 UID COPY 101:* Sent\r\n')
        transport.push_write(
            b'copy1 OK [COPYUID ', (br'\d+', ), b' 101:104 103:106]'
            b' UID COPY completed.\r\n')
        transport.push_select(b'Sent', 6, 4)
        transport.push_logout()
        await self.run(transport)

    async def test_copy_email_id(self, imap_server: IMAPServer) -> None:
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_select(b'INBOX')
        transport.push_readline(
            b'copy1 COPY 4 INBOX\r\n')
        transport.push_write(
            b'* 5 EXISTS\r\n'
            b'* 2 RECENT\r\n'
            b'* 5 FETCH (FLAGS (\\Recent))\r\n'
            b'copy1 OK [COPYUID ', (br'\d+', ), b' 104 105]'
            b' COPY completed.\r\n')
        transport.push_readline(
            b'fetch1 FETCH 4,5 (EMAILID THREADID)\r\n')
        transport.push_write(
            b'* 4 FETCH (EMAILID (', (br'M[a-f0-9]+', b'mid1'), b')'
            b' THREADID (', (br'T[a-f0-9]+', b'tid1'), b'))\r\n'
            b'* 5 FETCH (EMAILID (', (br'M[a-f0-9]+', b'mid2'), b')'
            b' THREADID (', (br'T[a-f0-9]+', b'tid2'), b'))\r\n'
            b'fetch1 OK FETCH completed.\r\n')
        transport.push_logout()
        await self.run(transport)
        assert self.matches['mid1'] == self.matches['mid2']
        assert self.matches['tid1'] == self.matches['tid2']

    async def test_concurrent_copy_fetch(self, imap_server: IMAPServer) \
            -> None:
        transport = self.new_transport(imap_server)
        concurrent = self.new_transport(imap_server)
        event1, event2, event3 = self.new_events(3)

        concurrent.push_login()
        concurrent.push_select(b'Sent', 2, 0, set=event1)
        concurrent.push_readline(
            b'noop1 NOOP\r\n', wait=event2)
        concurrent.push_write(
            b'* 6 EXISTS\r\n'
            b'* 4 RECENT\r\n'
            b'* 3 FETCH (FLAGS (\\Recent \\Seen))\r\n'
            b'* 4 FETCH (FLAGS (\\Answered \\Recent \\Seen))\r\n'
            b'* 5 FETCH (FLAGS (\\Flagged \\Recent))\r\n'
            b'* 6 FETCH (FLAGS (\\Recent))\r\n'
            b'noop1 OK NOOP completed.\r\n')
        concurrent.push_logout()

        transport.push_login()
        transport.push_select(b'INBOX', wait=event1, set=event2)
        transport.push_readline(
            b'copy1 COPY 1:* Sent\r\n')
        transport.push_write(
            b'copy1 OK [COPYUID ', (br'\d+', ), b' 101:104 103:106]'
            b' COPY completed.\r\n', set=event2)
        transport.push_logout()

        await self.run(transport, concurrent)

    async def test_move(self, imap_server: IMAPServer) -> None:
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_select(b'INBOX')
        transport.push_readline(
            b'move1 MOVE 1:* Sent\r\n')
        transport.push_write(
            b'* OK [COPYUID ', (br'\d+', ), b' 101:104 103:106] Moved.\r\n'
            b'* 4 EXPUNGE\r\n'
            b'* 3 EXPUNGE\r\n'
            b'* 2 EXPUNGE\r\n'
            b'* 1 EXPUNGE\r\n'
            b'* 0 RECENT\r\n'
            b'move1 OK MOVE completed.\r\n')
        transport.push_select(b'Sent', 6, 4)
        transport.push_logout()
        await self.run(transport)

    async def test_uid_move(self, imap_server: IMAPServer) -> None:
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_select(b'INBOX')
        transport.push_readline(
            b'move1 UID MOVE 101:* Sent\r\n')
        transport.push_write(
            b'* OK [COPYUID ', (br'\d+', ), b' 101:104 103:106] Moved.\r\n'
            b'* 4 EXPUNGE\r\n'
            b'* 3 EXPUNGE\r\n'
            b'* 2 EXPUNGE\r\n'
            b'* 1 EXPUNGE\r\n'
            b'* 0 RECENT\r\n'
            b'move1 OK UID MOVE completed.\r\n')
        transport.push_select(b'Sent', 6, 4)
        transport.push_logout()
        await self.run(transport)

    async def test_move_email_id(self, imap_server: IMAPServer) -> None:
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_select(b'INBOX')
        transport.push_readline(
            b'fetch1 FETCH 4 (EMAILID THREADID)\r\n')
        transport.push_write(
            b'* 4 FETCH (EMAILID (', (br'M[a-f0-9]+', b'mid1'), b')'
            b' THREADID (', (br'T[a-f0-9]+', b'tid1'), b'))\r\n'
            b'fetch1 OK FETCH completed.\r\n')
        transport.push_readline(
            b'move1 MOVE 4 Sent\r\n')
        transport.push_write(
            b'* OK [COPYUID ', (br'\d+', ), b' 104 103] Moved.\r\n'
            b'* 4 EXPUNGE\r\n'
            b'* 0 RECENT\r\n'
            b'move1 OK MOVE completed.\r\n')
        transport.push_select(b'Sent', 3, 1)
        transport.push_readline(
            b'fetch2 FETCH 3 (EMAILID THREADID)\r\n')
        transport.push_write(
            b'* 3 FETCH (EMAILID (', (br'M[a-f0-9]+', b'mid2'), b')'
            b' THREADID (', (br'T[a-f0-9]+', b'tid2'), b'))\r\n'
            b'fetch2 OK FETCH completed.\r\n')
        transport.push_logout()
        await self.run(transport)
        assert self.matches['mid1'] == self.matches['mid2']
        assert self.matches['tid1'] == self.matches['tid2']

    async def test_concurrent_move_fetch(self, imap_server: IMAPServer) \
            -> None:
        transport = self.new_transport(imap_server)
        concurrent = self.new_transport(imap_server)
        event1, event2, event3 = self.new_events(3)

        concurrent.push_login()
        concurrent.push_select(b'Sent', 2, 0, set=event1)
        concurrent.push_readline(
            b'noop1 NOOP\r\n', wait=event2)
        concurrent.push_write(
            b'* 4 EXISTS\r\n'
            b'* 2 RECENT\r\n'
            b'* 3 FETCH (FLAGS (\\Recent \\Seen))\r\n'
            b'* 4 FETCH (FLAGS (\\Recent))\r\n'
            b'noop1 OK NOOP completed.\r\n')
        concurrent.push_logout()

        transport.push_login()
        transport.push_select(b'INBOX', wait=event1, set=event2)
        transport.push_readline(
            b'move1 MOVE 1,4 Sent\r\n')
        transport.push_write(
            b'* OK [COPYUID ', (br'\d+', ), b' 101,104 103:104] Moved.\r\n'
            b'* 4 EXPUNGE\r\n'
            b'* 1 EXPUNGE\r\n'
            b'* 0 RECENT\r\n'
            b'move1 OK MOVE completed.\r\n', set=event2)
        transport.push_logout()

        await self.run(transport, concurrent)
