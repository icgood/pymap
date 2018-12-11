import pytest  # type: ignore

from .base import TestBase

pytestmark = pytest.mark.asyncio


class TestSearch(TestBase):

    async def test_search_disabled(self):
        self.transport.push_login()
        self.transport.push_select(b'INBOX')
        self.transport.push_readline(
            b'search1 SEARCH DRAFT\r\n')
        self.transport.push_write(
            b'search1 NO [CANNOT] SEARCH DRAFT not allowed.\r\n')
        self.transport.push_logout()
        await self.run()

    async def test_search(self):
        self.transport.push_login()
        self.transport.push_select(b'INBOX')
        self.transport.push_readline(
            b'search1 SEARCH ALL\r\n')
        self.transport.push_write(
            b'* SEARCH 1 2 3 4\r\n'
            b'search1 OK SEARCH completed.\r\n')
        self.transport.push_logout()
        await self.run()

    async def test_search_not(self):
        self.transport.push_login()
        self.transport.push_select(b'INBOX')
        self.transport.push_readline(
            b'search1 SEARCH NOT ALL\r\n')
        self.transport.push_write(
            b'* SEARCH\r\n'
            b'search1 OK SEARCH completed.\r\n')
        self.transport.push_logout()
        await self.run()

    async def test_search_uid(self):
        self.transport.push_login()
        self.transport.push_select(b'INBOX')
        self.transport.push_readline(
            b'search1 UID SEARCH ALL\r\n')
        self.transport.push_write(
            b'* SEARCH 101 102 103 104\r\n'
            b'search1 OK UID SEARCH completed.\r\n')
        self.transport.push_logout()
        await self.run()

    async def test_search_seqset(self):
        self.transport.push_login()
        self.transport.push_select(b'INBOX')
        self.transport.push_readline(
            b'search1 SEARCH 2:3\r\n')
        self.transport.push_write(
            b'* SEARCH 2 3\r\n'
            b'search1 OK SEARCH completed.\r\n')
        self.transport.push_logout()
        await self.run()

    async def test_search_and(self):
        self.transport.push_login()
        self.transport.push_select(b'INBOX')
        self.transport.push_readline(
            b'search1 SEARCH 1:3 2:4\r\n')
        self.transport.push_write(
            b'* SEARCH 2 3\r\n'
            b'search1 OK SEARCH completed.\r\n')
        self.transport.push_logout()
        await self.run()

    async def test_search_or(self):
        self.transport.push_login()
        self.transport.push_select(b'INBOX')
        self.transport.push_readline(
            b'search1 SEARCH OR 1 3:4\r\n')
        self.transport.push_write(
            b'* SEARCH 1 3 4\r\n'
            b'search1 OK SEARCH completed.\r\n')
        self.transport.push_logout()
        await self.run()

    async def test_search_seen(self):
        self.transport.push_login()
        self.transport.push_select(b'INBOX')
        self.transport.push_readline(
            b'search1 SEARCH SEEN\r\n')
        self.transport.push_write(
            b'* SEARCH 1 2\r\n'
            b'search1 OK SEARCH completed.\r\n')
        self.transport.push_logout()
        await self.run()

    async def test_search_unseen(self):
        self.transport.push_login()
        self.transport.push_select(b'INBOX')
        self.transport.push_readline(
            b'search1 SEARCH UNSEEN\r\n')
        self.transport.push_write(
            b'* SEARCH 3 4\r\n'
            b'search1 OK SEARCH completed.\r\n')
        self.transport.push_logout()
        await self.run()

    async def test_search_new(self):
        self.transport.push_login()
        self.transport.push_select(b'INBOX')
        self.transport.push_readline(
            b'search1 SEARCH NEW\r\n')
        self.transport.push_write(
            b'* SEARCH 4\r\n'
            b'search1 OK SEARCH completed.\r\n')
        self.transport.push_logout()
        await self.run()

    async def test_search_date_on(self):
        self.transport.push_login()
        self.transport.push_select(b'INBOX')
        self.transport.push_readline(
            b'search1 SEARCH ON 01-Jan-1990\r\n')
        self.transport.push_write(
            b'* SEARCH 2\r\n'
            b'search1 OK SEARCH completed.\r\n')
        self.transport.push_logout()
        await self.run()

    async def test_search_date_since(self):
        self.transport.push_login()
        self.transport.push_select(b'INBOX')
        self.transport.push_readline(
            b'search1 SEARCH SINCE 01-Jan-2000\r\n')
        self.transport.push_write(
            b'* SEARCH 3 4\r\n'
            b'search1 OK SEARCH completed.\r\n')
        self.transport.push_logout()
        await self.run()

    async def test_search_header_date(self):
        self.transport.push_login()
        self.transport.push_select(b'INBOX')
        self.transport.push_readline(
            b'search1 SEARCH SENTON 01-Jan-1990\r\n')
        self.transport.push_write(
            b'* SEARCH 2\r\n'
            b'search1 OK SEARCH completed.\r\n')
        self.transport.push_logout()
        await self.run()

    async def test_search_size(self):
        self.transport.push_login()
        self.transport.push_select(b'INBOX')
        self.transport.push_readline(
            b'search1 SEARCH SMALLER 1000\r\n')
        self.transport.push_write(
            b'* SEARCH 1 2 3\r\n'
            b'search1 OK SEARCH completed.\r\n')
        self.transport.push_logout()
        await self.run()

    async def test_search_from(self):
        self.transport.push_login()
        self.transport.push_select(b'INBOX')
        self.transport.push_readline(
            b'search1 SEARCH FROM "corp@example.com"\r\n')
        self.transport.push_write(
            b'* SEARCH 3\r\n'
            b'search1 OK SEARCH completed.\r\n')
        self.transport.push_logout()
        await self.run()

    async def test_search_subject(self):
        self.transport.push_login()
        self.transport.push_select(b'INBOX')
        self.transport.push_readline(
            b'search1 SEARCH SUBJECT "Hello"\r\n')
        self.transport.push_write(
            b'* SEARCH 4\r\n'
            b'search1 OK SEARCH completed.\r\n')
        self.transport.push_logout()
        await self.run()

    async def test_search_header(self):
        self.transport.push_login()
        self.transport.push_select(b'INBOX')
        self.transport.push_readline(
            b'search1 SEARCH HEADER "Priority" "high"\r\n')
        self.transport.push_write(
            b'* SEARCH 3\r\n'
            b'search1 OK SEARCH completed.\r\n')
        self.transport.push_logout()
        await self.run()

    async def test_search_body(self):
        self.transport.push_login()
        self.transport.push_select(b'INBOX')
        self.transport.push_readline(
            b'search1 SEARCH BODY "velocity"\r\n')
        self.transport.push_write(
            b'* SEARCH 2\r\n'
            b'search1 OK SEARCH completed.\r\n')
        self.transport.push_logout()
        await self.run()

    async def test_search_text(self):
        self.transport.push_login()
        self.transport.push_select(b'INBOX')
        self.transport.push_readline(
            b'search1 SEARCH TEXT "WORLD"\r\n')
        self.transport.push_write(
            b'* SEARCH 4\r\n'
            b'search1 OK SEARCH completed.\r\n')
        self.transport.push_logout()
        await self.run()
