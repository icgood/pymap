
from functools import partial

import pytest

from pymap.demo import init
from pymap.server import IMAPServer
from test.mocktransport import MockTransport

pytestmark = pytest.mark.asyncio


class TestServer:

    def setup_method(self):
        self.transport = MockTransport()
        self.run = partial(IMAPServer.callback,
            init(), self.transport, self.transport)

    def _login(self):
        self.transport.push_write(
            b'* OK [CAPABILITY IMAP4rev1 AUTH=PLAIN] Server ready ',
            (br'\S+', ), b'\r\n')
        self.transport.push_readline(
            b'login1 LOGIN demouser demopass\r\n')
        self.transport.push_write(
            b'login1 OK Authentication successful.\r\n')

    def _logout(self):
        self.transport.push_readline(
            b'logout1 LOGOUT\r\n')
        self.transport.push_write(
            b'* BYE Logging out.\r\n'
            b'logout1 OK Logout successful.\r\n')
        self.transport.push_write_close()

    def _select(self, mailbox, exists, recent, uidnext, unseen):
        self.transport.push_readline(
            b'select1 SELECT ' + mailbox + b'\r\n')
        self.transport.push_write(
            b'* OK [PERMANENTFLAGS (\\Answered \\Deleted \\Draft \\Flagged '
            b'\\Seen)] Flags permitted.\r\n* FLAGS (\\Answered \\Deleted '
            b'\\Draft \\Flagged \\Recent \\Seen)\r\n'
            b'* ', b'%i' % exists, b' EXISTS\r\n'
            b'* ', b'%i' % recent, b' RECENT\r\n'
            b'* OK [UIDNEXT ', b'%i' % uidnext, b'] Predicted next UID.\r\n'
            b'* OK [UIDVALIDITY ', (br'\d+', ), b'] Predicted next UID.\r\n'
            b'* OK [UNSEEN ', b'%i' % unseen, b'] First unseen message.\r\n'
            b'select1 OK [READ-WRITE] Selected mailbox.\r\n')

    async def test_login_logout(self):
        self._login()
        self._logout()
        await self.run()

    async def test_select(self):
        self._login()
        self._select(b'INBOX', 4, 1, 104, 4)
        self._logout()
        await self.run()

    async def test_select_clears_recent(self):
        self._login()
        self._select(b'INBOX', 4, 1, 104, 4)
        self._select(b'INBOX', 4, 0, 104, 4)
        self._logout()
        await self.run()

    async def test_list(self):
        self._login()
        self.transport.push_readline(
            b'list1 LIST "" ""\r\n')
        self.transport.push_write(
            b'* LIST () "." INBOX\r\n'
            b'* LIST () "." Sent\r\n'
            b'list1 OK LIST completed.\r\n')
        self._logout()
        await self.run()

    async def test_uid_fetch(self):
        self._login()
        self._select(b'INBOX', 4, 1, 104, 4)
        self.transport.push_readline(
            b'fetch1 UID FETCH 1:* (FLAGS)\r\n')
        self.transport.push_write(
            b'* 1 FETCH (FLAGS (\\Seen) UID 100)\r\n'
            b'* 2 FETCH (FLAGS (\\Answered \\Seen) UID 101)\r\n'
            b'* 3 FETCH (FLAGS (\\Flagged \\Seen) UID 102)\r\n'
            b'* 4 FETCH (FLAGS (\\Recent) UID 103)\r\n'
            b'fetch1 OK FETCH completed.\r\n')
        self._logout()
        await self.run()

    async def test_uid_store(self):
        self._login()
        self._select(b'INBOX', 4, 1, 104, 4)
        self.transport.push_readline(
            b'store1 UID STORE * +FlAGS (\\Seen)\r\n')
        self.transport.push_write(
            b'* 4 FETCH (FLAGS (\\Recent \\Seen) UID 103)\r\n'
            b'store1 OK STORE completed.\r\n')
        self._logout()
        await self.run()

    async def test_append(self):
        message = b'test message\r\n'
        self._login()
        self._select(b'INBOX', 4, 1, 104, 4)
        self.transport.push_readline(
            b'append1 APPEND INBOX (\\Seen) {%i}\r\n' % len(message))
        self.transport.push_write(
            b'+ Literal string\r\n')
        self.transport.push_readexactly(message)
        self.transport.push_readline(
            b'\r\n')
        self.transport.push_write(
            b'* 5 EXISTS\r\n'
            b'* 2 RECENT\r\n'
            b'* 5 FETCH (FLAGS (\\Recent \\Seen))\r\n'
            b'append1 OK APPEND completed.\r\n')
        self._logout()
        await self.run()

    async def test_expunge(self):
        self._login()
        self._select(b'INBOX', 4, 1, 104, 4)
        self.transport.push_readline(
            b'store1 STORE * +FlAGS (\\Deleted)\r\n')
        self.transport.push_write(
            b'* 4 FETCH (FLAGS (\\Deleted \\Recent))\r\n'
            b'store1 OK STORE completed.\r\n')
        self.transport.push_readline(
            b'expunge1 EXPUNGE\r\n')
        self.transport.push_write(
            b'* 4 EXPUNGE\r\n'
            b'* 3 EXISTS\r\n'
            b'* 0 RECENT\r\n'
            b'expunge1 OK EXPUNGE completed.\r\n')
        self._logout()
        await self.run()
