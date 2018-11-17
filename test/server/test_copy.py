
import pytest  # type: ignore

from .base import TestBase

pytestmark = pytest.mark.asyncio


class TestCopy(TestBase):

    async def test_copy(self):
        self.transport.push_login()
        self.transport.push_select(b'INBOX')
        self.transport.push_readline(
            b'copy1 COPY 1:* Sent\r\n')
        self.transport.push_write(
            b'copy1 OK [COPYUID ', (br'\d+', ), b' 101:104 102:105]'
            b' COPY completed.\r\n')
        self.transport.push_select(b'Sent', 5, 4)
        self.transport.push_logout()
        await self.run()

    async def test_uid_copy(self):
        self.transport.push_login()
        self.transport.push_select(b'INBOX')
        self.transport.push_readline(
            b'copy1 UID COPY 1:* Sent\r\n')
        self.transport.push_write(
            b'copy1 OK [COPYUID ', (br'\d+', ), b' 101:104 102:105]'
            b' UID COPY completed.\r\n')
        self.transport.push_select(b'Sent', 5, 4)
        self.transport.push_logout()
        await self.run()

    async def test_concurrent_copy_fetch(self):
        concurrent = self.new_transport()
        event1, event2, event3 = self.new_events(3)

        concurrent.push_login()
        concurrent.push_select(b'Sent', 1, 0, unseen=False, set=event1)
        concurrent.push_readline(
            b'noop1 NOOP\r\n', wait=event2)
        concurrent.push_write(
            b'* 5 EXISTS\r\n'
            b'* 4 RECENT\r\n'
            b'* 2 FETCH (FLAGS (\\Recent \\Seen))\r\n'
            b'* 3 FETCH (FLAGS (\\Answered \\Recent \\Seen))\r\n'
            b'* 4 FETCH (FLAGS (\\Flagged \\Recent))\r\n'
            b'* 5 FETCH (FLAGS (\\Recent))\r\n'
            b'noop1 OK NOOP completed.\r\n')
        concurrent.push_logout()

        self.transport.push_login()
        self.transport.push_select(b'INBOX', wait=event1, set=event2)
        self.transport.push_readline(
            b'copy1 COPY 1:* Sent\r\n')
        self.transport.push_write(
            b'copy1 OK [COPYUID ', (br'\d+', ), b' 101:104 102:105]'
            b' COPY completed.\r\n', set=event2)
        self.transport.push_logout()

        await self.run(concurrent)
