
import pytest  # type: ignore

from .base import TestBase

pytestmark = pytest.mark.asyncio


class TestMailbox(TestBase):

    async def test_list_sep(self, imap_server):
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_readline(
            b'list1 LIST "" ""\r\n')
        transport.push_write(
            b'* LIST (\\Noselect) "/" ""\r\n'
            b'list1 OK LIST completed.\r\n')
        transport.push_logout()
        await self.run(transport)

    async def test_list(self, imap_server):
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_readline(
            b'list1 LIST "" *\r\n')
        transport.push_write(
            b'* LIST (\\HasNoChildren) "/" INBOX\r\n'
            b'* LIST (\\HasNoChildren) "/" Sent\r\n'
            b'* LIST (\\HasNoChildren) "/" Trash\r\n'
            b'list1 OK LIST completed.\r\n')
        transport.push_logout()
        await self.run(transport)

    async def test_create(self, imap_server):
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_readline(
            b'create1 CREATE "test mailbox"\r\n')
        transport.push_write(
            b'create1 OK CREATE completed.\r\n')
        transport.push_readline(
            b'list1 LIST "" *\r\n')
        transport.push_write(
            b'* LIST (\\HasNoChildren) "/" INBOX\r\n'
            b'* LIST (\\HasNoChildren) "/" Sent\r\n'
            b'* LIST (\\HasNoChildren) "/" Trash\r\n'
            b'* LIST (\\HasNoChildren) "/" "test mailbox"\r\n'
            b'list1 OK LIST completed.\r\n')
        transport.push_logout()
        await self.run(transport)

    async def test_create_inferior(self, imap_server):
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_readline(
            b'create1 CREATE "Trash/test mailbox"\r\n')
        transport.push_write(
            b'create1 OK CREATE completed.\r\n')
        transport.push_readline(
            b'list1 LIST "Trash" *\r\n')
        transport.push_write(
            b'* LIST (\\HasChildren) "/" Trash\r\n'
            b'* LIST (\\HasNoChildren) "/" "Trash/test mailbox"\r\n'
            b'list1 OK LIST completed.\r\n')
        transport.push_logout()
        await self.run(transport)

    async def test_delete(self, imap_server):
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_readline(
            b'delete1 DELETE Sent\r\n')
        transport.push_write(
            b'delete1 OK DELETE completed.\r\n')
        transport.push_readline(
            b'list2 LIST "" *\r\n')
        transport.push_write(
            b'* LIST (\\HasNoChildren) "/" INBOX\r\n'
            b'* LIST (\\HasNoChildren) "/" Trash\r\n'
            b'list2 OK LIST completed.\r\n')
        transport.push_logout()
        await self.run(transport)

    async def test_delete_superior(self, imap_server):
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_readline(
            b'create1 CREATE "Trash/test mailbox"\r\n')
        transport.push_write(
            b'create1 OK CREATE completed.\r\n')
        transport.push_readline(
            b'delete1 DELETE Trash\r\n')
        transport.push_write(
            b'delete1 OK DELETE completed.\r\n')
        transport.push_readline(
            b'list1 LIST "Trash" *\r\n')
        transport.push_write(
            b'* LIST (\\Noselect \\HasChildren) "/" Trash\r\n'
            b'* LIST (\\HasNoChildren) "/" "Trash/test mailbox"\r\n'
            b'list1 OK LIST completed.\r\n')
        transport.push_logout()
        await self.run(transport)

    async def test_delete_selected(self, imap_server):
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_select(b'Sent')
        transport.push_readline(
            b'delete1 DELETE Sent\r\n')
        transport.push_write(
            b'* BYE Selected mailbox deleted.\r\n'
            b'delete1 OK DELETE completed.\r\n')
        await self.run(transport)

    async def test_rename(self, imap_server):
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

    async def test_rename_inbox(self, imap_server):
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

    async def test_rename_inbox_selected(self, imap_server):
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_select(b'INBOX')
        transport.push_readline(
            b'rename1 RENAME INBOX "Inbox Test"\r\n')
        transport.push_write(
            b'* BYE [UIDVALIDITY ', (br'\d+', ), b'] UID validity changed.\r\n'
            b'rename1 OK RENAME completed.\r\n')
        await self.run(transport)

    async def test_rename_selected(self, imap_server):
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_select(b'Sent')
        transport.push_readline(
            b'rename1 RENAME Sent "Sent Test"\r\n')
        transport.push_write(
            b'* BYE Selected mailbox deleted.\r\n'
            b'rename1 OK RENAME completed.\r\n')
        await self.run(transport)

    async def test_lsub(self, imap_server):
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_readline(
            b'lsub1 LSUB "" *\r\n')
        transport.push_write(
            b'* LSUB (\\HasNoChildren) "/" INBOX\r\n'
            b'lsub1 OK LSUB completed.\r\n')
        transport.push_logout()
        await self.run(transport)

    async def test_subscribe_unsubscribe(self, imap_server):
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_readline(
            b'subscribe1 SUBSCRIBE "Sent"\r\n')
        transport.push_write(
            b'subscribe1 OK SUBSCRIBE completed.\r\n')
        transport.push_readline(
            b'subscribe2 SUBSCRIBE "Trash"\r\n')
        transport.push_write(
            b'subscribe2 OK SUBSCRIBE completed.\r\n')
        transport.push_readline(
            b'unsubscribe1 UNSUBSCRIBE "Trash"\r\n')
        transport.push_write(
            b'unsubscribe1 OK UNSUBSCRIBE completed.\r\n')
        transport.push_readline(
            b'lsub1 LSUB "" *\r\n')
        transport.push_write(
            b'* LSUB (\\HasNoChildren) "/" INBOX\r\n'
            b'* LSUB (\\HasNoChildren) "/" Sent\r\n'
            b'lsub1 OK LSUB completed.\r\n')
        transport.push_logout()
        await self.run(transport)

    async def test_status(self, imap_server):
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_readline(
            b'status1 STATUS INBOX '
            b'(MESSAGES RECENT UIDNEXT UIDVALIDITY UNSEEN)\r\n')
        transport.push_write(
            b'* STATUS INBOX (MESSAGES 4 RECENT 1 UIDNEXT 105 '
            b'UIDVALIDITY ', (br'\d+', b'uidval1'), b' UNSEEN 2)\r\n'
            b'status1 OK STATUS completed.\r\n')
        transport.push_select(b'INBOX', 4, 1, 105, 3)
        transport.push_readline(
            b'status2 STATUS INBOX '
            b'(MESSAGES RECENT UIDNEXT UIDVALIDITY UNSEEN)\r\n')
        transport.push_write(
            b'* STATUS INBOX (MESSAGES 4 RECENT 1 UIDNEXT 105 '
            b'UIDVALIDITY ', (br'\d+', b'uidval2'), b' UNSEEN 2)\r\n'
            b'status2 OK STATUS completed.\r\n')
        transport.push_readline(
            b'close1 CLOSE\r\n')
        transport.push_write(
            b'close1 OK CLOSE completed.\r\n')
        transport.push_readline(
            b'status3 STATUS INBOX '
            b'(MESSAGES RECENT UIDNEXT UIDVALIDITY UNSEEN)\r\n')
        transport.push_write(
            b'* STATUS INBOX (MESSAGES 4 RECENT 0 UIDNEXT 105 '
            b'UIDVALIDITY ', (br'\d+', b'uidval2'), b' UNSEEN 2)\r\n'
            b'status3 OK STATUS completed.\r\n')
        transport.push_logout()
        await self.run(transport)
        assert self.matches['uidval1'] == self.matches['uidval2']

    async def test_append(self, imap_server):
        transport = self.new_transport(imap_server)
        message = b'test message\r\n'
        transport.push_login()
        transport.push_readline(
            b'append1 APPEND INBOX (\\Seen) {%i}\r\n' % len(message))
        transport.push_write(
            b'+ Literal string\r\n')
        transport.push_readexactly(message)
        transport.push_readline(
            b'\r\n')
        transport.push_write(
            b'append1 OK [APPENDUID ', (br'\d+', ), b' 105]'
            b' APPEND completed.\r\n')
        transport.push_select(b'INBOX', 5, 2, 106, 3)
        transport.push_logout()
        await self.run(transport)

    async def test_append_empty(self, imap_server):
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_readline(
            b'append1 APPEND INBOX {0}\r\n')
        transport.push_write(
            b'+ Literal string\r\n')
        transport.push_readexactly(
            b'')
        transport.push_readline(
            b'\r\n')
        transport.push_write(
            b'append1 NO APPEND cancelled.\r\n')
        transport.push_select(b'INBOX', 4, 1, 105, 3)
        transport.push_logout()
        await self.run(transport)

    async def test_append_multi(self, imap_server):
        transport = self.new_transport(imap_server)
        message_1 = b'test message\r\n'
        message_2 = b'test message\r\n'
        transport.push_login()
        transport.push_readline(
            b'append1 APPEND INBOX (\\Seen) {%i}\r\n' % len(message_1))
        transport.push_write(
            b'+ Literal string\r\n')
        transport.push_readexactly(message_1)
        transport.push_readline(
            b' {%i}\r\n' % len(message_2))
        transport.push_write(
            b'+ Literal string\r\n')
        transport.push_readexactly(message_2)
        transport.push_readline(
            b'\r\n')
        transport.push_write(
            b'append1 OK [APPENDUID ', (br'\d+', ), b' 105:106]'
            b' APPEND completed.\r\n')
        transport.push_select(b'INBOX', 6, 3, 107, 3)
        transport.push_logout()
        await self.run(transport)

    async def test_append_selected(self, imap_server):
        transport = self.new_transport(imap_server)
        message = b'test message\r\n'
        transport.push_login()
        transport.push_select(b'INBOX', 4, 1, 105, 3)
        transport.push_readline(
            b'append1 APPEND INBOX (\\Seen) {%i}\r\n' % len(message))
        transport.push_write(
            b'+ Literal string\r\n')
        transport.push_readexactly(message)
        transport.push_readline(
            b'\r\n')
        transport.push_write(
            b'* 5 EXISTS\r\n'
            b'* 2 RECENT\r\n'
            b'* 5 FETCH (FLAGS (\\Recent \\Seen))\r\n'
            b'append1 OK [APPENDUID ', (br'\d+', ), b' 105]'
            b' APPEND completed.\r\n')
        transport.push_readline(
            b'status1 STATUS INBOX (RECENT)\r\n')
        transport.push_write(
            b'* STATUS INBOX (RECENT 2)\r\n'
            b'status1 OK STATUS completed.\r\n')
        transport.push_logout()
        await self.run(transport)
