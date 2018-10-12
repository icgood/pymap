
import pytest  # type: ignore

from .base import TestBase

pytestmark = pytest.mark.asyncio


class TestFetch(TestBase):

    async def test_uid_fetch(self):
        self.transport.push_login()
        self.transport.push_select(b'INBOX')
        self.transport.push_readline(
            b'fetch1 UID FETCH 1:* (FLAGS)\r\n')
        self.transport.push_write(
            b'* 1 FETCH (FLAGS (\\Seen) UID 100)\r\n'
            b'* 2 FETCH (FLAGS (\\Answered \\Seen) UID 101)\r\n'
            b'* 3 FETCH (FLAGS (\\Flagged \\Seen) UID 102)\r\n'
            b'* 4 FETCH (FLAGS (\\Recent) UID 103)\r\n'
            b'fetch1 OK FETCH completed.\r\n')
        self.transport.push_logout()
        await self.run()

    async def test_fetch_full(self):
        self.transport.push_login()
        self.transport.push_select(b'INBOX')
        self.transport.push_readline(
            b'fetch1 FETCH * FULL\r\n')
        self.transport.push_write(
            b'* 4 FETCH (FLAGS (\\Recent) '
            b'INTERNALDATE "01-Jan-2010 00:00:00" '
            b'RFC822.SIZE 2048 '
            b'ENVELOPE ("01-Jan-2010 01:01:00 +0000" "Hello, World!" '
            b'(("" NIL "friend" "example.com")) '
            b'(("" NIL "friend" "example.com")) '
            b'(("" NIL "friend" "example.com")) '
            b'(("" NIL "me" "example.com")) NIL NIL NIL NIL) '
            b'BODY ("text" "plain" NIL NIL NIL NIL 2048 38))\r\n'
            b'fetch1 OK FETCH completed.\r\n')
        self.transport.push_logout()
        await self.run()

    async def test_fetch_bodystructure(self):
        self.transport.push_login()
        self.transport.push_select(b'INBOX')
        self.transport.push_readline(
            b'fetch1 FETCH * (BODYSTRUCTURE)\r\n')
        self.transport.push_write(
            b'* 4 FETCH (BODYSTRUCTURE ("text" "plain" NIL NIL NIL NIL '
            b'2048 38 NIL NIL NIL NIL))\r\n'
            b'fetch1 OK FETCH completed.\r\n')
        self.transport.push_logout()
        await self.run()

    async def test_fetch_rfc822(self):
        self.transport.push_login()
        self.transport.push_select(b'INBOX')
        self.transport.push_readline(
            b'fetch1 FETCH 1 (RFC822)\r\n')
        self.transport.push_write(
            b'* 1 FETCH (RFC822 {192}\r\n'
            b'From: friend@example.com\r\n'
            b'To: me@example.com\r\n'
            b'Subject: Re: Re: Random question\r\n'
            b'Content-Type: text/plain\r\n'
            b'Date: 01-Jan-1970 01:01:00 +0000\r\n\r\n'
            b"Well, I don't know that!\r\n\r\n"
            b'*AAAAAGGGGGHHHHHH*\r\n'
            b'\r\n)\r\n'
            b'fetch1 OK FETCH completed.\r\n')
        self.transport.push_logout()
        await self.run()

    async def test_fetch_rfc822_header(self):
        self.transport.push_login()
        self.transport.push_select(b'INBOX')
        self.transport.push_readline(
            b'fetch1 FETCH 1 (RFC822.HEADER)\r\n')
        self.transport.push_write(
            b'* 1 FETCH (RFC822.HEADER {147}\r\n'
            b'From: friend@example.com\r\n'
            b'To: me@example.com\r\n'
            b'Subject: Re: Re: Random question\r\n'
            b'Content-Type: text/plain\r\n'
            b'Date: Thu, 01 Jan 1970 01:01:00 +0000\r\n'
            b'\r\n)\r\n'
            b'fetch1 OK FETCH completed.\r\n')
        self.transport.push_logout()
        await self.run()

    async def test_fetch_rfc822_text(self):
        self.transport.push_login()
        self.transport.push_select(b'INBOX')
        self.transport.push_readline(
            b'fetch1 FETCH 1 (RFC822.TEXT)\r\n')
        self.transport.push_write(
            b'* 1 FETCH (RFC822.TEXT {50}\r\n'
            b"Well, I don't know that!\r\n\r\n"
            b'*AAAAAGGGGGHHHHHH*\r\n'
            b'\r\n)\r\n'
            b'fetch1 OK FETCH completed.\r\n')
        self.transport.push_logout()
        await self.run()
