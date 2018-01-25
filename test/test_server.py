
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
            b'. SELECT ' + mailbox + b'\r\n')
        self.transport.push_write(
            b'* OK [PERMANENTFLAGS (\\Answered \\Deleted \\Draft \\Flagged '
            b'\\Seen)] Flags permitted.\r\n* FLAGS (\\Answered \\Deleted '
            b'\\Draft \\Flagged \\Recent \\Seen)\r\n'
            b'* ', b'%i' % exists, b' EXISTS\r\n'
            b'* ', b'%i' % recent, b' RECENT\r\n'
            b'* OK [UIDNEXT ', b'%i' % uidnext, b'] Predicted next UID.\r\n'
            b'* OK [UIDVALIDITY ', (br'\d+', ), b'] Predicted next UID.\r\n'
            b'* OK [UNSEEN ', b'%i' % unseen, b'] First unseen message.\r\n'
            b'. OK [READ-WRITE] Selected mailbox.\r\n')

    async def test_login_logout(self):
        self._login()
        self._logout()
        await self.run()

    async def test_select(self):
        self._login()
        self._select(b'INBOX', 4, 1, 5, 4)
        self._logout()
        await self.run()
