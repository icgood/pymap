
from io import BytesIO
from argparse import ArgumentParser, Namespace
from typing import Any, Optional

import pytest  # type: ignore

from pymap.admin.handlers import AdminHandlers
from pymap.admin.grpc.admin_pb2 import AppendRequest, AppendResponse, \
    SUCCESS, ERROR_RESPONSE
from pymap.admin.client.append import AppendCommand

from .base import TestBase

pytestmark = pytest.mark.asyncio


class _Stream:

    def __init__(self, request) -> None:
        self.request = request
        self.response: Optional[Any] = None

    async def recv_message(self) -> object:
        return self.request

    async def send_message(self, response) -> None:
        self.response = response


class _Stub:

    def __init__(self, response) -> None:
        self.method: Optional[str] = None
        self.request: Optional[Any] = None
        self.response = response

    async def _action(self, request):
        self.request = request
        return self.response

    def __getattr__(self, method):
        self.method = method
        return self._action


class TestAdminHandlers(TestBase):

    async def test_append(self, backend, imap_server):
        handlers = AdminHandlers(backend)
        data = b'From: user@example.com\n\ntest message!\n'
        request = AppendRequest(user='testuser', mailbox='INBOX',
                                flags=['\\Flagged', '\\Seen'],
                                when=1234567890, data=data)
        stream = _Stream(request)
        await handlers.Append(stream)
        response: AppendResponse = stream.response
        assert SUCCESS == response.result
        assert 105 == response.uid

        transport = self.new_transport(imap_server)
        transport.push_login()
        transport.push_select(b'INBOX')
        transport.push_readline(
            b'fetch1 UID FETCH * FULL\r\n')
        transport.push_write(
            b'* 5 FETCH (FLAGS (\\Flagged \\Recent \\Seen)'
            b' INTERNALDATE "13-Feb-2009 23:31:30 +0000"'
            b' RFC822.SIZE 38'
            b' ENVELOPE (NIL NIL (("" NIL "user" "example.com"))'
            b' (("" NIL "user" "example.com")) (("" NIL "user" "example.com"))'
            b' NIL NIL NIL NIL NIL)'
            b' BODY ("text" "plain" NIL NIL NIL "7BIT" 38 3)'
            b' UID 105)\r\n'
            b'fetch1 OK UID FETCH completed.\r\n')
        transport.push_logout()
        await self.run(transport)

    async def test_append_user_not_found(self, backend):
        handlers = AdminHandlers(backend)
        request = AppendRequest(user='baduser')
        stream = _Stream(request)
        await handlers.Append(stream)
        response: AppendResponse = stream.response
        assert ERROR_RESPONSE == response.result
        assert 'InvalidAuth' == response.error_type

    async def test_append_mailbox_not_found(self, backend):
        handlers = AdminHandlers(backend)
        request = AppendRequest(user='testuser', mailbox='BAD')
        stream = _Stream(request)
        await handlers.Append(stream)
        response: AppendResponse = stream.response
        assert ERROR_RESPONSE == response.result
        assert 'BAD' == response.mailbox
        assert 'MailboxNotFound' == response.error_type

    async def test_append_filter_reject(self, backend):
        handlers = AdminHandlers(backend)
        data = b'Subject: reject this\n\ntest message!\n'
        request = AppendRequest(user='testuser', mailbox='INBOX',
                                flags=['\\Flagged', '\\Seen'],
                                when=1234567890, data=data)
        stream = _Stream(request)
        await handlers.Append(stream)
        response: AppendResponse = stream.response
        assert ERROR_RESPONSE == response.result
        assert 'AppendFailure' == response.error_type

    async def test_append_filter_discard(self, backend):
        handlers = AdminHandlers(backend)
        data = b'Subject: discard this\n\ntest message!\n'
        request = AppendRequest(user='testuser', mailbox='INBOX',
                                flags=['\\Flagged', '\\Seen'],
                                when=1234567890, data=data)
        stream = _Stream(request)
        await handlers.Append(stream)
        response: AppendResponse = stream.response
        assert SUCCESS == response.result
        assert not response.mailbox
        assert not response.uid

    async def test_append_filter_address_is(self, backend):
        handlers = AdminHandlers(backend)
        data = b'From: foo@example.com\n\ntest message!\n'
        request = AppendRequest(user='testuser', mailbox='INBOX',
                                flags=['\\Flagged', '\\Seen'],
                                when=1234567890, data=data)
        stream = _Stream(request)
        await handlers.Append(stream)
        response: AppendResponse = stream.response
        assert 'Test 1' == response.mailbox

    async def test_append_filter_address_contains(self, backend):
        handlers = AdminHandlers(backend)
        data = b'From: user@foo.com\n\ntest message!\n'
        request = AppendRequest(user='testuser', mailbox='INBOX',
                                flags=['\\Flagged', '\\Seen'],
                                when=1234567890, data=data)
        stream = _Stream(request)
        await handlers.Append(stream)
        response: AppendResponse = stream.response
        assert 'Test 2' == response.mailbox

    async def test_append_filter_address_matches(self, backend):
        handlers = AdminHandlers(backend)
        data = b'To: bigfoot@example.com\n\ntest message!\n'
        request = AppendRequest(user='testuser', mailbox='INBOX',
                                flags=['\\Flagged', '\\Seen'],
                                when=1234567890, data=data)
        stream = _Stream(request)
        await handlers.Append(stream)
        response: AppendResponse = stream.response
        assert 'Test 3' == response.mailbox

    async def test_append_filter_envelope_is(self, backend):
        handlers = AdminHandlers(backend)
        data = b'From: user@example.com\n\ntest message!\n'
        request = AppendRequest(user='testuser', mailbox='INBOX',
                                sender='foo@example.com', recipient=None,
                                flags=['\\Flagged', '\\Seen'],
                                when=1234567890, data=data)
        stream = _Stream(request)
        await handlers.Append(stream)
        response: AppendResponse = stream.response
        assert 'Test 4' == response.mailbox

    async def test_append_filter_envelope_contains(self, backend):
        handlers = AdminHandlers(backend)
        data = b'From: user@example.com\n\ntest message!\n'
        request = AppendRequest(user='testuser', mailbox='INBOX',
                                sender='user@foo.com', recipient=None,
                                flags=['\\Flagged', '\\Seen'],
                                when=1234567890, data=data)
        stream = _Stream(request)
        await handlers.Append(stream)
        response: AppendResponse = stream.response
        assert 'Test 5' == response.mailbox

    async def test_append_filter_envelope_matches(self, backend):
        handlers = AdminHandlers(backend)
        data = b'From: user@example.com\n\ntest message!\n'
        request = AppendRequest(user='testuser', mailbox='INBOX',
                                sender=None, recipient='bigfoot@example.com',
                                flags=['\\Flagged', '\\Seen'],
                                when=1234567890, data=data)
        stream = _Stream(request)
        await handlers.Append(stream)
        response: AppendResponse = stream.response
        assert 'Test 6' == response.mailbox

    async def test_append_filter_exists(self, backend):
        handlers = AdminHandlers(backend)
        data = b'X-Foo: foo\nX-Bar: bar\n\ntest message!\n'
        request = AppendRequest(user='testuser', mailbox='INBOX',
                                flags=['\\Flagged', '\\Seen'],
                                when=1234567890, data=data)
        stream = _Stream(request)
        await handlers.Append(stream)
        response: AppendResponse = stream.response
        assert 'Test 7' == response.mailbox

    async def test_append_filter_header(self, backend):
        handlers = AdminHandlers(backend)
        data = b'X-Caffeine: C8H10N4O2\n\ntest message!\n'
        request = AppendRequest(user='testuser', mailbox='INBOX',
                                flags=['\\Flagged', '\\Seen'],
                                when=1234567890, data=data)
        stream = _Stream(request)
        await handlers.Append(stream)
        response: AppendResponse = stream.response
        assert 'Test 8' == response.mailbox

    async def test_append_filter_size(self, backend):
        handlers = AdminHandlers(backend)
        data = b'From: user@example.com\n\ntest message!\n'
        data = data + b'x' * (1234 - len(data))
        request = AppendRequest(user='testuser', mailbox='INBOX',
                                flags=['\\Flagged', '\\Seen'],
                                when=1234567890, data=data)
        stream = _Stream(request)
        await handlers.Append(stream)
        response: AppendResponse = stream.response
        assert 'Test 9' == response.mailbox


class TestAdminClient:

    async def test_append(self):
        parser = ArgumentParser()
        subparsers = parser.add_subparsers(dest='test')
        name, command = AppendCommand.init(parser, subparsers)
        stub = _Stub('append response')
        args = Namespace(user='testuser', sender=None, recipient=None,
                         mailbox='INBOX', data=BytesIO(b'test data'),
                         flags=['\\Flagged', '\\Seen'],
                         timestamp=1234567890)
        response = await command.run(stub, args)
        request = stub.request
        assert 'Append' == stub.method
        assert 'append response' == response
        assert b'test data' == request.data
        assert 1234567890.0 == request.when
        assert ['\\Flagged', '\\Seen'] == request.flags
        assert 'testuser' == request.user
        assert 'INBOX' == request.mailbox
