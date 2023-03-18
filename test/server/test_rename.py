
from .base import TestBase

from pymap.imap import IMAPServer


class TestMailbox(TestBase):

    async def test_rename(self, imap_server: IMAPServer) -> None:
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_readline(
            b'status1 STATUS Sent (MESSAGES UIDNEXT UIDVALIDITY)\r\n')
        transport.push_write(
            b'* STATUS Sent (MESSAGES 2 UIDNEXT 103 '
            b'UIDVALIDITY ', (br'\d+', b'uidval1'), b')\r\n'
            b'status1 OK STATUS completed.\r\n')
        transport.push_readline(
            b'rename1 RENAME Sent "Sent Test"\r\n')
        transport.push_write(
            b'rename1 OK RENAME completed.\r\n')
        transport.push_readline(
            b'status1 STATUS Sent (MESSAGES)\r\n')
        transport.push_write(
            b'status1 NO [NONEXISTENT] Mailbox does not exist.\r\n')
        transport.push_readline(
            b'status1 STATUS "Sent Test" (MESSAGES UIDNEXT UIDVALIDITY)\r\n')
        transport.push_write(
            b'* STATUS "Sent Test" (MESSAGES 2 UIDNEXT 103 '
            b'UIDVALIDITY ', (br'\d+', b'uidval2'), b')\r\n'
            b'status1 OK STATUS completed.\r\n')
        transport.push_logout()
        await self.run(transport)
        assert self.matches['uidval1'] == self.matches['uidval2']

    async def test_rename_inbox(self, imap_server: IMAPServer) -> None:
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_readline(
            b'status1 STATUS INBOX (MESSAGES UIDNEXT UIDVALIDITY)\r\n')
        transport.push_write(
            b'* STATUS INBOX (MESSAGES 4 UIDNEXT 105 '
            b'UIDVALIDITY ', (br'\d+', b'uidval1'), b')\r\n'
            b'status1 OK STATUS completed.\r\n')
        transport.push_readline(
            b'rename1 RENAME INBOX "Inbox Test"\r\n')
        transport.push_write(
            b'rename1 OK RENAME completed.\r\n')
        transport.push_readline(
            b'status1 STATUS INBOX (MESSAGES UIDNEXT UIDVALIDITY)\r\n')
        transport.push_write(
            b'* STATUS INBOX (MESSAGES 0 UIDNEXT 101 '
            b'UIDVALIDITY ', (br'\d+', b'uidval2'), b')\r\n'
            b'status1 OK STATUS completed.\r\n')
        transport.push_readline(
            b'status1 STATUS "Inbox Test" (MESSAGES UIDNEXT UIDVALIDITY)\r\n')
        transport.push_write(
            b'* STATUS "Inbox Test" (MESSAGES 4 UIDNEXT 105 '
            b'UIDVALIDITY ', (br'\d+', b'uidval3'), b')\r\n'
            b'status1 OK STATUS completed.\r\n')
        transport.push_logout()
        await self.run(transport)
        assert self.matches['uidval1'] != self.matches['uidval2']
        assert self.matches['uidval1'] == self.matches['uidval3']

    async def test_rename_inbox_selected(self, imap_server: IMAPServer) \
            -> None:
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_select(b'INBOX')
        transport.push_readline(
            b'rename1 RENAME INBOX "Inbox Test"\r\n')
        transport.push_write(
            b'rename1 OK RENAME completed.\r\n')
        transport.push_select(b'INBOX', 0, 0, 101, False)
        transport.push_logout()
        await self.run(transport)

    async def test_rename_other_selected(self, imap_server: IMAPServer) \
            -> None:
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_select(b'Sent')
        transport.push_readline(
            b'rename1 RENAME Sent "Sent Test"\r\n')
        transport.push_write(
            b'* BYE Selected mailbox no longer exists.\r\n'
            b'rename1 OK RENAME completed.\r\n')
        await self.run(transport)

    async def test_rename_selected(self, imap_server: IMAPServer) -> None:
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_select(b'Sent')
        transport.push_readline(
            b'rename1 RENAME Sent "Sent Test"\r\n')
        transport.push_write(
            b'* BYE Selected mailbox no longer exists.\r\n'
            b'rename1 OK RENAME completed.\r\n')
        await self.run(transport)

    async def test_rename_inferior(self, imap_server: IMAPServer) -> None:
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_readline(
            b'create1 CREATE Test\r\n')
        transport.push_write(
            b'create1 OK [MAILBOXID (', (br'F[a-f0-9]+', ), b')]'
            b' CREATE completed.\r\n')
        transport.push_readline(
            b'create2 CREATE Test/One\r\n')
        transport.push_write(
            b'create2 OK [MAILBOXID (', (br'F[a-f0-9]+', ), b')]'
            b' CREATE completed.\r\n')
        transport.push_readline(
            b'create3 CREATE Test/One/Two\r\n')
        transport.push_write(
            b'create3 OK [MAILBOXID (', (br'F[a-f0-9]+', ), b')]'
            b' CREATE completed.\r\n')
        transport.push_readline(
            b'delete1 DELETE Test/One\r\n')
        transport.push_write(
            b'delete1 OK DELETE completed.\r\n')
        transport.push_readline(
            b'rename1 RENAME Test Foo\r\n')
        transport.push_write(
            b'rename1 OK RENAME completed.\r\n')
        transport.push_readline(
            b'list1 LIST Test *\r\n')
        transport.push_write(
            b'list1 OK LIST completed.\r\n')
        transport.push_readline(
            b'list2 LIST Foo *\r\n')
        transport.push_write(
            b'* LIST (\\HasChildren) "/" Foo\r\n'
            b'* LIST (\\Noselect \\HasChildren) "/" Foo/One\r\n'
            b'* LIST (\\HasNoChildren) "/" Foo/One/Two\r\n'
            b'list2 OK LIST completed.\r\n')
        transport.push_logout()
        await self.run(transport)

    async def test_rename_mailbox_id(self, imap_server: IMAPServer) -> None:
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_readline(
            b'create1 CREATE Test\r\n')
        transport.push_write(
            b'create1 OK [MAILBOXID (', (br'F[a-f0-9]+', b'mbxid'), b')]'
            b' CREATE completed.\r\n')
        transport.push_readline(
            b'rename1 RENAME Test Foo\r\n')
        transport.push_write(
            b'rename1 OK RENAME completed.\r\n')
        transport.push_select(b'Foo', unseen=False)
        transport.push_logout()
        await self.run(transport)
        assert self.matches['mbxid1'] == self.matches['mbxid']
