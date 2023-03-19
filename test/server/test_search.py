
import pytest

from .base import TestBase

from pymap.imap import IMAPServer


class TestSearch(TestBase):

    @pytest.fixture
    def overrides(self):
        return {'disable_search_keys': [b'DRAFT']}

    async def test_search_disabled(self, imap_server: IMAPServer) -> None:
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_select(b'INBOX')
        transport.push_readline(
            b'search1 SEARCH DRAFT\r\n')
        transport.push_write(
            b'search1 NO [CANNOT] SEARCH DRAFT not supported.\r\n')
        transport.push_logout()
        await self.run(transport)

    async def test_search(self, imap_server: IMAPServer) -> None:
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_select(b'INBOX')
        transport.push_readline(
            b'search1 SEARCH ALL\r\n')
        transport.push_write(
            b'* SEARCH 1 2 3 4\r\n'
            b'search1 OK SEARCH completed.\r\n')
        transport.push_logout()
        await self.run(transport)

    async def test_search_not(self, imap_server: IMAPServer) -> None:
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_select(b'INBOX')
        transport.push_readline(
            b'search1 SEARCH NOT ALL\r\n')
        transport.push_write(
            b'* SEARCH\r\n'
            b'search1 OK SEARCH completed.\r\n')
        transport.push_logout()
        await self.run(transport)

    async def test_search_uid(self, imap_server: IMAPServer) -> None:
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_select(b'INBOX')
        transport.push_readline(
            b'search1 UID SEARCH ALL\r\n')
        transport.push_write(
            b'* SEARCH 101 102 103 104\r\n'
            b'search1 OK UID SEARCH completed.\r\n')
        transport.push_logout()
        await self.run(transport)

    async def test_search_seqset(self, imap_server: IMAPServer) -> None:
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_select(b'INBOX')
        transport.push_readline(
            b'search1 SEARCH 2:3\r\n')
        transport.push_write(
            b'* SEARCH 2 3\r\n'
            b'search1 OK SEARCH completed.\r\n')
        transport.push_logout()
        await self.run(transport)

    async def test_search_and(self, imap_server: IMAPServer) -> None:
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_select(b'INBOX')
        transport.push_readline(
            b'search1 SEARCH 1:3 2:4\r\n')
        transport.push_write(
            b'* SEARCH 2 3\r\n'
            b'search1 OK SEARCH completed.\r\n')
        transport.push_logout()
        await self.run(transport)

    async def test_search_or(self, imap_server: IMAPServer) -> None:
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_select(b'INBOX')
        transport.push_readline(
            b'search1 SEARCH OR 1 3:4\r\n')
        transport.push_write(
            b'* SEARCH 1 3 4\r\n'
            b'search1 OK SEARCH completed.\r\n')
        transport.push_logout()
        await self.run(transport)

    async def test_search_seen(self, imap_server: IMAPServer) -> None:
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_select(b'INBOX')
        transport.push_readline(
            b'search1 SEARCH SEEN\r\n')
        transport.push_write(
            b'* SEARCH 1 2\r\n'
            b'search1 OK SEARCH completed.\r\n')
        transport.push_logout()
        await self.run(transport)

    async def test_search_unseen(self, imap_server: IMAPServer) -> None:
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_select(b'INBOX')
        transport.push_readline(
            b'search1 SEARCH UNSEEN\r\n')
        transport.push_write(
            b'* SEARCH 3 4\r\n'
            b'search1 OK SEARCH completed.\r\n')
        transport.push_logout()
        await self.run(transport)

    async def test_search_new(self, imap_server: IMAPServer) -> None:
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_select(b'INBOX')
        transport.push_readline(
            b'search1 SEARCH NEW\r\n')
        transport.push_write(
            b'* SEARCH 4\r\n'
            b'search1 OK SEARCH completed.\r\n')
        transport.push_logout()
        await self.run(transport)

    async def test_search_date_on(self, imap_server: IMAPServer) -> None:
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_select(b'INBOX')
        transport.push_readline(
            b'search1 SEARCH ON 01-Jan-1990\r\n')
        transport.push_write(
            b'* SEARCH 2\r\n'
            b'search1 OK SEARCH completed.\r\n')
        transport.push_logout()
        await self.run(transport)

    async def test_search_date_since(self, imap_server: IMAPServer) -> None:
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_select(b'INBOX')
        transport.push_readline(
            b'search1 SEARCH SINCE 01-Jan-2000\r\n')
        transport.push_write(
            b'* SEARCH 3 4\r\n'
            b'search1 OK SEARCH completed.\r\n')
        transport.push_logout()
        await self.run(transport)

    async def test_search_header_date(self, imap_server: IMAPServer) -> None:
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_select(b'INBOX')
        transport.push_readline(
            b'search1 SEARCH SENTON 01-Jan-1990\r\n')
        transport.push_write(
            b'* SEARCH 2\r\n'
            b'search1 OK SEARCH completed.\r\n')
        transport.push_logout()
        await self.run(transport)

    async def test_search_size(self, imap_server: IMAPServer) -> None:
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_select(b'INBOX')
        transport.push_readline(
            b'search1 SEARCH SMALLER 1000\r\n')
        transport.push_write(
            b'* SEARCH 1 2 3\r\n'
            b'search1 OK SEARCH completed.\r\n')
        transport.push_logout()
        await self.run(transport)

    async def test_search_from(self, imap_server: IMAPServer) -> None:
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_select(b'INBOX')
        transport.push_readline(
            b'search1 SEARCH FROM "corp@example.com"\r\n')
        transport.push_write(
            b'* SEARCH 3\r\n'
            b'search1 OK SEARCH completed.\r\n')
        transport.push_logout()
        await self.run(transport)

    async def test_search_subject(self, imap_server: IMAPServer) -> None:
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_select(b'INBOX')
        transport.push_readline(
            b'search1 SEARCH SUBJECT "Hello"\r\n')
        transport.push_write(
            b'* SEARCH 4\r\n'
            b'search1 OK SEARCH completed.\r\n')
        transport.push_logout()
        await self.run(transport)

    async def test_search_header(self, imap_server: IMAPServer) -> None:
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_select(b'INBOX')
        transport.push_readline(
            b'search1 SEARCH HEADER "Priority" "high"\r\n')
        transport.push_write(
            b'* SEARCH 3\r\n'
            b'search1 OK SEARCH completed.\r\n')
        transport.push_logout()
        await self.run(transport)

    async def test_search_body(self, imap_server: IMAPServer) -> None:
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_select(b'INBOX')
        transport.push_readline(
            b'search1 SEARCH BODY "velocity"\r\n')
        transport.push_write(
            b'* SEARCH 2\r\n'
            b'search1 OK SEARCH completed.\r\n')
        transport.push_logout()
        await self.run(transport)

    async def test_search_text(self, imap_server: IMAPServer) -> None:
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_select(b'INBOX')
        transport.push_readline(
            b'search1 SEARCH TEXT "WORLD"\r\n')
        transport.push_write(
            b'* SEARCH 4\r\n'
            b'search1 OK SEARCH completed.\r\n')
        transport.push_logout()
        await self.run(transport)

    async def test_search_emailid(self, imap_server: IMAPServer) -> None:
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_select(b'INBOX')
        transport.push_readline(
            b'fetch1 FETCH 1,2 (EMAILID)\r\n')
        transport.push_write(
            b'* 1 FETCH (EMAILID (', (b'M[a-f0-9]+', b'id1'), b'))\r\n'
            b'* 2 FETCH (EMAILID (', (b'M[a-f0-9]+', b'id2'), b'))\r\n'
            b'fetch1 OK FETCH completed.\r\n')
        transport.push_readline(
            b'search1 SEARCH EMAILID %(id1)b\r\n')
        transport.push_write(
            b'* SEARCH 1\r\n'
            b'search1 OK SEARCH completed.\r\n')
        transport.push_readline(
            b'search2 SEARCH EMAILID %(id2)b\r\n')
        transport.push_write(
            b'* SEARCH 2\r\n'
            b'search2 OK SEARCH completed.\r\n')
        transport.push_logout()
        await self.run(transport)

    async def test_search_threadid(self, imap_server: IMAPServer) -> None:
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_select(b'INBOX')
        transport.push_readline(
            b'fetch1 FETCH 1,2 (THREADID)\r\n')
        transport.push_write(
            b'* 1 FETCH (THREADID (', (b'T[a-f0-9]+', b'id1'), b'))\r\n'
            b'* 2 FETCH (THREADID (', (b'T[a-f0-9]+', b'id2'), b'))\r\n'
            b'fetch1 OK FETCH completed.\r\n')
        transport.push_readline(
            b'search1 SEARCH THREADID %(id1)b\r\n')
        transport.push_write(
            b'* SEARCH 1\r\n'
            b'search1 OK SEARCH completed.\r\n')
        transport.push_readline(
            b'search2 SEARCH THREADID %(id2)b\r\n')
        transport.push_write(
            b'* SEARCH 2\r\n'
            b'search2 OK SEARCH completed.\r\n')
        transport.push_logout()
        await self.run(transport)
