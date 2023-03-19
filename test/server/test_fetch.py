
from .base import TestBase

from pymap.imap import IMAPServer


class TestFetch(TestBase):

    async def test_uid_fetch(self, imap_server: IMAPServer) -> None:
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_select(b'INBOX')
        transport.push_readline(
            b'fetch1 UID FETCH 1:* (FLAGS)\r\n')
        transport.push_write(
            b'* 1 FETCH (FLAGS (\\Seen) UID 101)\r\n'
            b'* 2 FETCH (FLAGS (\\Answered \\Seen) UID 102)\r\n'
            b'* 3 FETCH (FLAGS (\\Flagged) UID 103)\r\n'
            b'* 4 FETCH (FLAGS (\\Recent) UID 104)\r\n'
            b'fetch1 OK UID FETCH completed.\r\n')
        transport.push_logout()
        await self.run(transport)

    async def test_fetch_full(self, imap_server: IMAPServer) -> None:
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_select(b'INBOX')
        transport.push_readline(
            b'fetch1 FETCH * FULL\r\n')
        transport.push_write(
            b'* 4 FETCH (FLAGS (\\Recent) '
            b'INTERNALDATE "01-Jan-2010 00:00:00 +0000" '
            b'RFC822.SIZE 1980 '
            b'ENVELOPE ("01-Jan-2010 01:01:00 +0000" "Hello, World!" '
            b'(("" NIL "friend" "example.com")) '
            b'(("" NIL "friend" "example.com")) '
            b'(("" NIL "friend" "example.com")) '
            b'(("" NIL "me" "example.com")) NIL NIL NIL NIL) '
            b'BODY ("text" "plain" NIL NIL NIL "7BIT" 1980 38))\r\n'
            b'fetch1 OK FETCH completed.\r\n')
        transport.push_logout()
        await self.run(transport)

    async def test_fetch_bodystructure(self, imap_server: IMAPServer) -> None:
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_select(b'INBOX')
        transport.push_readline(
            b'fetch1 FETCH * (BODYSTRUCTURE)\r\n')
        transport.push_write(
            b'* 4 FETCH (BODYSTRUCTURE ("text" "plain" NIL NIL NIL "7BIT" '
            b'1980 38 NIL NIL NIL NIL))\r\n'
            b'fetch1 OK FETCH completed.\r\n')
        transport.push_logout()
        await self.run(transport)

    async def test_fetch_body_section(self, imap_server: IMAPServer) -> None:
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_select(b'INBOX')
        transport.push_readline(
            b'fetch1 FETCH 3 (FLAGS)\r\n')
        transport.push_write(
            b'* 3 FETCH (FLAGS (\\Flagged))\r\n'
            b'fetch1 OK FETCH completed.\r\n')
        transport.push_readline(
            b'fetch2 FETCH 3 (BODY[])\r\n')
        transport.push_write(
            b'* 3 FETCH (BODY[] {205}\r\n'
            b'From: corp@example.com\r\n'
            b'To: me@example.com\r\n'
            b'Subject: Important notice regarding your account\r\n'
            b'Priority: high\r\n'
            b'Content-Type: text/plain\r\n'
            b'Date: 01-Jan-2000 01:01:00 +0000\r\n\r\n'
            b'This is some important stuff!\r\n\r\n'
            b' FLAGS (\\Flagged \\Seen))\r\n'
            b'fetch2 OK FETCH completed.\r\n')
        transport.push_logout()
        await self.run(transport)

    async def test_fetch_rfc822(self, imap_server: IMAPServer) -> None:
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_select(b'INBOX')
        transport.push_readline(
            b'fetch1 FETCH 3 (FLAGS)\r\n')
        transport.push_write(
            b'* 3 FETCH (FLAGS (\\Flagged))\r\n'
            b'fetch1 OK FETCH completed.\r\n')
        transport.push_readline(
            b'fetch2 FETCH 3 (RFC822)\r\n')
        transport.push_write(
            b'* 3 FETCH (RFC822 {205}\r\n'
            b'From: corp@example.com\r\n'
            b'To: me@example.com\r\n'
            b'Subject: Important notice regarding your account\r\n'
            b'Priority: high\r\n'
            b'Content-Type: text/plain\r\n'
            b'Date: 01-Jan-2000 01:01:00 +0000\r\n\r\n'
            b'This is some important stuff!\r\n\r\n'
            b' FLAGS (\\Flagged \\Seen))\r\n'
            b'fetch2 OK FETCH completed.\r\n')
        transport.push_logout()
        await self.run(transport)

    async def test_fetch_rfc822_header(self, imap_server: IMAPServer) -> None:
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_select(b'INBOX')
        transport.push_readline(
            b'fetch1 FETCH 1 (RFC822.HEADER)\r\n')
        transport.push_write(
            b'* 1 FETCH (RFC822.HEADER {142}\r\n'
            b'From: friend@example.com\r\n'
            b'To: me@example.com\r\n'
            b'Subject: Re: Re: Random question\r\n'
            b'Content-Type: text/plain\r\n'
            b'Date: 01-Jan-1970 01:01:00 +0000\r\n'
            b'\r\n)\r\n'
            b'fetch1 OK FETCH completed.\r\n')
        transport.push_logout()
        await self.run(transport)

    async def test_fetch_rfc822_text(self, imap_server: IMAPServer) -> None:
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_select(b'INBOX')
        transport.push_readline(
            b'fetch1 FETCH 3 (FLAGS)\r\n')
        transport.push_write(
            b'* 3 FETCH (FLAGS (\\Flagged))\r\n'
            b'fetch1 OK FETCH completed.\r\n')
        transport.push_readline(
            b'fetch2 FETCH 3 (RFC822.TEXT)\r\n')
        transport.push_write(
            b'* 3 FETCH (RFC822.TEXT {33}\r\n'
            b'This is some important stuff!\r\n\r\n'
            b' FLAGS (\\Flagged \\Seen))\r\n'
            b'fetch2 OK FETCH completed.\r\n')
        transport.push_logout()
        await self.run(transport)

    async def test_fetch_body_section_header(self, imap_server: IMAPServer) \
            -> None:
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_select(b'Sent')
        transport.push_readline(
            b'fetch1 FETCH 2 (BODY[3.HEADER])\r\n')
        transport.push_write(
            b'* 2 FETCH (BODY[3.HEADER] {172}\r\n'
            b'From: corp@example.com\r\n'
            b'To: me@example.com\r\n'
            b'Subject: Important notice regarding your account\r\n'
            b'Priority: high\r\n'
            b'Content-Type: text/plain\r\n'
            b'Date: 01-Jan-2000 01:01:00 +0000\r\n'
            b'\r\n FLAGS (\\Draft \\Seen))\r\n'
            b'fetch1 OK FETCH completed.\r\n')
        transport.push_readline(
            b'fetch2 FETCH 2 (BODY[1.HEADER])\r\n')
        transport.push_write(
            b'* 2 FETCH (BODY[1.HEADER] {0}\r\n'
            b')\r\n'
            b'fetch2 OK FETCH completed.\r\n')
        transport.push_logout()
        await self.run(transport)

    async def test_fetch_body_section_header_fields(
            self, imap_server: IMAPServer) -> None:
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_select(b'Sent')
        transport.push_readline(
            b'fetch1 FETCH 2 (BODY[3.HEADER.FIELDS (FROM TO DATE)])\r\n')
        transport.push_write(
            b'* 2 FETCH (BODY[3.HEADER.FIELDS (DATE FROM TO)] {80}\r\n'
            b'From: corp@example.com\r\n'
            b'To: me@example.com\r\n'
            b'Date: 01-Jan-2000 01:01:00 +0000\r\n'
            b'\r\n FLAGS (\\Draft \\Seen))\r\n'
            b'fetch1 OK FETCH completed.\r\n')
        transport.push_logout()
        await self.run(transport)

    async def test_fetch_body_section_text(
            self, imap_server: IMAPServer) -> None:
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_select(b'Sent')
        transport.push_readline(
            b'fetch1 FETCH 2 (FLAGS)\r\n')
        transport.push_write(
            b'* 2 FETCH (FLAGS (\\Draft))\r\n'
            b'fetch1 OK FETCH completed.\r\n')
        transport.push_readline(
            b'fetch2 FETCH 2 (BODY[3.TEXT])\r\n')
        transport.push_write(
            b'* 2 FETCH (BODY[3.TEXT] {33}\r\n'
            b'This is some important stuff!\r\n\r\n'
            b' FLAGS (\\Draft \\Seen))\r\n'
            b'fetch2 OK FETCH completed.\r\n')
        transport.push_readline(
            b'fetch3 FETCH 2 (BODY[1.TEXT])\r\n')
        transport.push_write(
            b'* 2 FETCH (BODY[1.TEXT] {0}\r\n'
            b')\r\n'
            b'fetch3 OK FETCH completed.\r\n')
        transport.push_logout()
        await self.run(transport)

    async def test_fetch_binary_section(self, imap_server: IMAPServer) -> None:
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_select(b'Sent')
        transport.push_readline(
            b'fetch1 FETCH 2 (BINARY.SIZE[1] BINARY[1])\r\n')
        transport.push_write(
            b'* 2 FETCH (BINARY.SIZE[1] 28 BINARY[1] ~{28}\r\n'
            + 'ᎻéⅬⅬՕ ᎳоᏒⅬⅮ'.encode('utf-8') +
            b' FLAGS (\\Draft \\Seen))\r\n'
            b'fetch1 OK FETCH completed.\r\n')
        transport.push_readline(
            b'fetch2 FETCH 2 (BINARY.SIZE[2] BINARY[2])\r\n')
        transport.push_write(
            b'* 2 FETCH (BINARY.SIZE[2] 16 BINARY[2] ~{16}\r\n'
            + 'foo=bar+ßaz\r\n\r\n'.encode('utf-8') +
            b')\r\n'
            b'fetch2 OK FETCH completed.\r\n')
        transport.push_logout()
        await self.run(transport)

    async def test_fetch_binary_section_partial(
            self, imap_server: IMAPServer) -> None:
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_select(b'Sent')
        transport.push_readline(
            b'fetch1 FETCH 2 (BINARY[1]<5.17>)\r\n')
        transport.push_write(
            b'* 2 FETCH (BINARY[1]<5> ~{17}\r\n'
            + 'ⅬⅬՕ ᎳоᏒ'.encode('utf-8') +
            b' FLAGS (\\Draft \\Seen))\r\n'
            b'fetch1 OK FETCH completed.\r\n')
        transport.push_logout()
        await self.run(transport)

    async def test_append_fetch_binary(self, imap_server: IMAPServer) -> None:
        transport = self.new_transport(imap_server)
        message = b'\r\ntest\x00message\r\n'
        transport.push_login()
        transport.push_readline(
            b'append1 APPEND INBOX (\\Seen) ~{%i}\r\n' % len(message))
        transport.push_write(
            b'+ Literal string\r\n')
        transport.push_readexactly(message)
        transport.push_readline(
            b'\r\n')
        transport.push_write(
            b'append1 OK [APPENDUID ', (br'\d+', ), b' 105]'
            b' APPEND completed.\r\n')
        transport.push_select(b'INBOX', 5, 2, 106, 3)
        transport.push_readline(
            b'fetch1 FETCH 5 (BINARY[] BINARY.SIZE[])\r\n')
        transport.push_write(
            b'* 5 FETCH (BINARY[] ~{16}\r\n'
            b'\r\ntest\x00message\r\n'
            b' BINARY.SIZE[] 16)\r\n'
            b'fetch1 OK FETCH completed.\r\n')
        transport.push_logout()
        await self.run(transport)

    async def test_fetch_email_id(self, imap_server: IMAPServer) -> None:
        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_select(b'INBOX')
        transport.push_readline(
            b'fetch1 FETCH 1:* (EMAILID)\r\n')
        transport.push_write(
            b'* 1 FETCH (EMAILID (', (br'M[a-f0-9]+', b'id1'), b'))\r\n'
            b'* 2 FETCH (EMAILID (', (br'M[a-f0-9]+', b'id2'), b'))\r\n'
            b'* 3 FETCH (EMAILID (', (br'M[a-f0-9]+', b'id3'), b'))\r\n'
            b'* 4 FETCH (EMAILID (', (br'M[a-f0-9]+', b'id4'), b'))\r\n'
            b'fetch1 OK FETCH completed.\r\n')
        transport.push_readline(
            b'fetch2 FETCH 1:* (EMAILID)\r\n')
        transport.push_write(
            b'* 1 FETCH (EMAILID (', (br'M[a-f0-9]+', b'id5'), b'))\r\n'
            b'* 2 FETCH (EMAILID (', (br'M[a-f0-9]+', b'id6'), b'))\r\n'
            b'* 3 FETCH (EMAILID (', (br'M[a-f0-9]+', b'id7'), b'))\r\n'
            b'* 4 FETCH (EMAILID (', (br'M[a-f0-9]+', b'id8'), b'))\r\n'
            b'fetch2 OK FETCH completed.\r\n')
        transport.push_logout()
        await self.run(transport)
        assert len({self.matches[f'id{n}'] for n in range(1, 5)}) == 4
        for n in range(1, 5):
            assert self.matches[f'id{n}'] == self.matches[f'id{n+4}']
