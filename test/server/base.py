
from functools import partial

from pymap.demo import init
from pymap.server import IMAPServer
from .mocktransport import MockTransport


class TestBase:

    def setup_method(self):
        self.matches = {}
        self.transport = MockTransport(self.matches)
        self.run = partial(IMAPServer.callback,
            init(), self.transport, self.transport)

    def login(self):
        self.transport.push_write(
            b'* OK [CAPABILITY IMAP4rev1 AUTH=PLAIN] Server ready ',
            (br'\S+', ), b'\r\n')
        self.transport.push_readline(
            b'login1 LOGIN demouser demopass\r\n')
        self.transport.push_write(
            b'login1 OK Authentication successful.\r\n')

    def logout(self):
        self.transport.push_readline(
            b'logout1 LOGOUT\r\n')
        self.transport.push_write(
            b'* BYE Logging out.\r\n'
            b'logout1 OK Logout successful.\r\n')
        self.transport.push_write_close()

    def select(self, mailbox, exists, recent, uidnext, unseen):
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
