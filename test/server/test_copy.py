
import pytest  # type: ignore

from .base import TestBase

pytestmark = pytest.mark.asyncio


class TestCopy(TestBase):

    async def test_copy(self, imap_server):
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

    async def test_uid_copy(self, imap_server):
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_select(b'INBOX')
        transport.push_readline(
            b'copy1 UID COPY 1:* Sent\r\n')
        transport.push_write(
            b'copy1 OK [COPYUID ', (br'\d+', ), b' 101:104 103:106]'
            b' UID COPY completed.\r\n')
        transport.push_select(b'Sent', 6, 4)
        transport.push_logout()
        await self.run(transport)

    async def test_concurrent_copy_fetch(self, imap_server):
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
