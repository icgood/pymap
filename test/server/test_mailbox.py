
import pytest  # type: ignore

from .base import TestBase

pytestmark = pytest.mark.asyncio


class TestMailbox(TestBase):

    async def test_list_sep(self):
        self.transport.push_login()
        self.transport.push_readline(
            b'list1 LIST "" ""\r\n')
        self.transport.push_write(
            b'* LIST (\\Noselect) "." ""\r\n'
            b'list1 OK LIST completed.\r\n')
        self.transport.push_logout()
        await self.run()

    async def test_list(self):
        self.transport.push_login()
        self.transport.push_readline(
            b'list1 LIST "" *\r\n')
        self.transport.push_write(
            b'* LIST (\\HasNoChildren) "." INBOX\r\n'
            b'* LIST (\\HasNoChildren) "." Sent\r\n'
            b'* LIST (\\HasNoChildren) "." Trash\r\n'
            b'list1 OK LIST completed.\r\n')
        self.transport.push_logout()
        await self.run()

    async def test_create(self):
        self.transport.push_login()
        self.transport.push_readline(
            b'create1 CREATE "test mailbox"\r\n')
        self.transport.push_write(
            b'create1 OK Mailbox created successfully.\r\n')
        self.transport.push_readline(
            b'list1 LIST "" *\r\n')
        self.transport.push_write(
            b'* LIST (\\HasNoChildren) "." INBOX\r\n'
            b'* LIST (\\HasNoChildren) "." Sent\r\n'
            b'* LIST (\\HasNoChildren) "." Trash\r\n'
            b'* LIST (\\HasNoChildren) "." "test mailbox"\r\n'
            b'list1 OK LIST completed.\r\n')
        self.transport.push_logout()
        await self.run()

    async def test_create_inferior(self):
        self.transport.push_login()
        self.transport.push_readline(
            b'create1 CREATE "Trash.test mailbox"\r\n')
        self.transport.push_write(
            b'create1 OK Mailbox created successfully.\r\n')
        self.transport.push_readline(
            b'list1 LIST "Trash" *\r\n')
        self.transport.push_write(
            b'* LIST (\\HasChildren) "." Trash\r\n'
            b'* LIST (\\HasNoChildren) "." "Trash.test mailbox"\r\n'
            b'list1 OK LIST completed.\r\n')
        self.transport.push_logout()
        await self.run()

    async def test_delete(self):
        self.transport.push_login()
        self.transport.push_readline(
            b'delete1 DELETE Sent\r\n')
        self.transport.push_write(
            b'delete1 OK Mailbox deleted successfully.\r\n')
        self.transport.push_readline(
            b'list2 LIST "" *\r\n')
        self.transport.push_write(
            b'* LIST (\\HasNoChildren) "." INBOX\r\n'
            b'* LIST (\\HasNoChildren) "." Trash\r\n'
            b'list2 OK LIST completed.\r\n')
        self.transport.push_logout()
        await self.run()

    async def test_delete_superior(self):
        self.transport.push_login()
        self.transport.push_readline(
            b'create1 CREATE "Trash.test mailbox"\r\n')
        self.transport.push_write(
            b'create1 OK Mailbox created successfully.\r\n')
        self.transport.push_readline(
            b'delete1 DELETE Trash\r\n')
        self.transport.push_write(
            b'delete1 OK Mailbox deleted successfully.\r\n')
        self.transport.push_readline(
            b'list1 LIST "Trash" *\r\n')
        self.transport.push_write(
            b'* LIST (\\Noselect \\HasChildren) "." Trash\r\n'
            b'* LIST (\\HasNoChildren) "." "Trash.test mailbox"\r\n'
            b'list1 OK LIST completed.\r\n')
        self.transport.push_logout()
        await self.run()

    async def test_delete_selected(self):
        self.transport.push_login()
        self.transport.push_select(b'Sent', unseen=False)
        self.transport.push_readline(
            b'delete1 DELETE Sent\r\n')
        self.transport.push_write(
            b'* BYE Selected mailbox deleted.\r\n'
            b'delete1 OK Mailbox deleted successfully.\r\n')
        self.transport.push_write_close()
        await self.run()

    async def test_rename(self):
        self.transport.push_login()
        self.transport.push_readline(
            b'status1 STATUS Sent (MESSAGES UIDNEXT UIDVALIDITY)\r\n')
        self.transport.push_write(
            b'* STATUS Sent (MESSAGES 1 UIDNEXT 102 '
            b'UIDVALIDITY ', (br'\d+', b'uidval1'), b')\r\n'
            b'status1 OK STATUS completed.\r\n')
        self.transport.push_readline(
            b'rename1 RENAME Sent "Sent Test"\r\n')
        self.transport.push_write(
            b'rename1 OK Mailbox renamed successfully.\r\n')
        self.transport.push_readline(
            b'status1 STATUS Sent (MESSAGES)\r\n')
        self.transport.push_write(
            b'status1 NO Mailbox does not exist.\r\n')
        self.transport.push_readline(
            b'status1 STATUS "Sent Test" (MESSAGES UIDNEXT UIDVALIDITY)\r\n')
        self.transport.push_write(
            b'* STATUS "Sent Test" (MESSAGES 1 UIDNEXT 102 '
            b'UIDVALIDITY ', (br'\d+', b'uidval2'), b')\r\n'
            b'status1 OK STATUS completed.\r\n')
        self.transport.push_logout()
        await self.run()
        assert self.matches['uidval1'] == self.matches['uidval2']

    async def test_rename_inbox(self):
        self.transport.push_login()
        self.transport.push_readline(
            b'status1 STATUS INBOX (MESSAGES UIDNEXT UIDVALIDITY)\r\n')
        self.transport.push_write(
            b'* STATUS INBOX (MESSAGES 4 UIDNEXT 105 '
            b'UIDVALIDITY ', (br'\d+', b'uidval1'), b')\r\n'
            b'status1 OK STATUS completed.\r\n')
        self.transport.push_readline(
            b'rename1 RENAME INBOX "Inbox Test"\r\n')
        self.transport.push_write(
            b'rename1 OK Mailbox renamed successfully.\r\n')
        self.transport.push_readline(
            b'status1 STATUS INBOX (MESSAGES UIDNEXT UIDVALIDITY)\r\n')
        self.transport.push_write(
            b'* STATUS INBOX (MESSAGES 0 UIDNEXT 101 '
            b'UIDVALIDITY ', (br'\d+', b'uidval2'), b')\r\n'
            b'status1 OK STATUS completed.\r\n')
        self.transport.push_readline(
            b'status1 STATUS "Inbox Test" (MESSAGES UIDNEXT UIDVALIDITY)\r\n')
        self.transport.push_write(
            b'* STATUS "Inbox Test" (MESSAGES 4 UIDNEXT 105 '
            b'UIDVALIDITY ', (br'\d+', b'uidval3'), b')\r\n'
            b'status1 OK STATUS completed.\r\n')
        self.transport.push_logout()
        await self.run()
        assert self.matches['uidval1'] != self.matches['uidval2']
        assert self.matches['uidval1'] == self.matches['uidval3']

    async def test_rename_inbox_selected(self):
        self.transport.push_login()
        self.transport.push_select(b'INBOX')
        self.transport.push_readline(
            b'rename1 RENAME INBOX "Inbox Test"\r\n')
        self.transport.push_write(
            b'* BYE [UIDVALIDITY ', (br'\d+', ), b'] UID validity changed.\r\n'
            b'rename1 OK Mailbox renamed successfully.\r\n')
        self.transport.push_write_close()
        await self.run()

    async def test_rename_selected(self):
        self.transport.push_login()
        self.transport.push_select(b'Sent', unseen=False)
        self.transport.push_readline(
            b'rename1 RENAME Sent "Sent Test"\r\n')
        self.transport.push_write(
            b'* BYE Selected mailbox deleted.\r\n'
            b'rename1 OK Mailbox renamed successfully.\r\n')
        self.transport.push_write_close()
        await self.run()

    async def test_lsub(self):
        self.transport.push_login()
        self.transport.push_readline(
            b'lsub1 LSUB "" *\r\n')
        self.transport.push_write(
            b'* LSUB (\\HasNoChildren) "." INBOX\r\n'
            b'lsub1 OK LSUB completed.\r\n')
        self.transport.push_logout()
        await self.run()

    async def test_subscribe_unsubscribe(self):
        self.transport.push_login()
        self.transport.push_readline(
            b'subscribe1 SUBSCRIBE "Sent"\r\n')
        self.transport.push_write(
            b'subscribe1 OK SUBSCRIBE completed.\r\n')
        self.transport.push_readline(
            b'subscribe2 SUBSCRIBE "Trash"\r\n')
        self.transport.push_write(
            b'subscribe2 OK SUBSCRIBE completed.\r\n')
        self.transport.push_readline(
            b'unsubscribe1 UNSUBSCRIBE "Trash"\r\n')
        self.transport.push_write(
            b'unsubscribe1 OK UNSUBSCRIBE completed.\r\n')
        self.transport.push_readline(
            b'lsub1 LSUB "" *\r\n')
        self.transport.push_write(
            b'* LSUB (\\HasNoChildren) "." INBOX\r\n'
            b'* LSUB (\\HasNoChildren) "." Sent\r\n'
            b'lsub1 OK LSUB completed.\r\n')
        self.transport.push_logout()
        await self.run()

    async def test_status(self):
        self.transport.push_login()
        self.transport.push_readline(
            b'status1 STATUS INBOX '
            b'(MESSAGES RECENT UIDNEXT UIDVALIDITY UNSEEN)\r\n')
        self.transport.push_write(
            b'* STATUS INBOX (MESSAGES 4 RECENT 1 UIDNEXT 105 '
            b'UIDVALIDITY ', (br'\d+', b'uidval1'), b' UNSEEN 1)\r\n'
            b'status1 OK STATUS completed.\r\n')
        self.transport.push_select(b'INBOX', 4, 1, 105, 4)
        self.transport.push_readline(
            b'status2 STATUS INBOX '
            b'(MESSAGES RECENT UIDNEXT UIDVALIDITY UNSEEN)\r\n')
        self.transport.push_write(
            b'* STATUS INBOX (MESSAGES 4 RECENT 0 UIDNEXT 105 '
            b'UIDVALIDITY ', (br'\d+', b'uidval2'), b' UNSEEN 1)\r\n'
            b'status2 OK STATUS completed.\r\n')
        self.transport.push_logout()
        await self.run()
        assert self.matches['uidval1'] == self.matches['uidval2']

    async def test_append(self):
        message = b'test message\r\n'
        self.transport.push_login()
        self.transport.push_readline(
            b'append1 APPEND INBOX (\\Seen) {%i}\r\n' % len(message))
        self.transport.push_write(
            b'+ Literal string\r\n')
        self.transport.push_readexactly(message)
        self.transport.push_readline(
            b'\r\n')
        self.transport.push_write(
            b'append1 OK [APPENDUID ', (br'\d+', ), b' 105]'
            b' APPEND completed.\r\n')
        self.transport.push_select(b'INBOX', 5, 2, 106, 4)
        self.transport.push_logout()
        await self.run()

    async def test_append_empty(self):
        self.transport.push_login()
        self.transport.push_readline(
            b'append1 APPEND INBOX {0}\r\n')
        self.transport.push_write(
            b'+ Literal string\r\n')
        self.transport.push_readexactly(
            b'')
        self.transport.push_readline(
            b'\r\n')
        self.transport.push_write(
            b'append1 NO APPEND cancelled.\r\n')
        self.transport.push_select(b'INBOX', 4, 1, 105, 4)
        self.transport.push_logout()
        await self.run()

    async def test_append_multi(self):
        message_1 = b'test message\r\n'
        message_2 = b'test message\r\n'
        self.transport.push_login()
        self.transport.push_readline(
            b'append1 APPEND INBOX (\\Seen) {%i}\r\n' % len(message_1))
        self.transport.push_write(
            b'+ Literal string\r\n')
        self.transport.push_readexactly(message_1)
        self.transport.push_readline(
            b' {%i}\r\n' % len(message_2))
        self.transport.push_write(
            b'+ Literal string\r\n')
        self.transport.push_readexactly(message_2)
        self.transport.push_readline(
            b'\r\n')
        self.transport.push_write(
            b'append1 OK [APPENDUID ', (br'\d+', ), b' 105:106]'
            b' APPEND completed.\r\n')
        self.transport.push_select(b'INBOX', 6, 3, 107, 4)
        self.transport.push_logout()
        await self.run()

    async def test_append_selected(self):
        message = b'test message\r\n'
        self.transport.push_login()
        self.transport.push_select(b'INBOX', 4, 1, 105, 4)
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
            b'append1 OK [APPENDUID ', (br'\d+', ), b' 105]'
            b' APPEND completed.\r\n')
        self.transport.push_logout()
        await self.run()
