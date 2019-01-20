
from io import BytesIO
from argparse import ArgumentParser, Namespace
from typing import Any, Optional

import pytest  # type: ignore

from pymap.admin.handlers import GrpcHandlers
from pymap.admin.grpc.admin_pb2 import AppendRequest, AppendResponse, \
    SUCCESS, USER_NOT_FOUND, MAILBOX_NOT_FOUND
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

    async def test_append(self):
        handlers = GrpcHandlers(self.backend)
        data = b'From: user@example.com\n\ntest message!\n'
        request = AppendRequest(user='testuser', mailbox='INBOX',
                                flags=['\\Flagged', '\\Seen'],
                                when=1234567890.0, data=data)
        stream = _Stream(request)
        await handlers.Append(stream)
        response: AppendResponse = stream.response
        assert SUCCESS == response.result
        assert 105 == response.uid

        self.transport.push_login()
        self.transport.push_select(b'INBOX')
        self.transport.push_readline(
            b'fetch1 UID FETCH * FULL\r\n')
        self.transport.push_write(
            b'* 5 FETCH (FLAGS (\\Flagged \\Recent \\Seen)'
            b' INTERNALDATE "13-Feb-2009 23:31:30 +0000"'
            b' RFC822.SIZE 38'
            b' ENVELOPE (NIL NIL (("" NIL "user" "example.com"))'
            b' (("" NIL "user" "example.com")) (("" NIL "user" "example.com"))'
            b' NIL NIL NIL NIL NIL)'
            b' BODY ("text" "plain" NIL NIL NIL "7BIT" 38 3)'
            b' UID 105)\r\n'
            b'fetch1 OK UID FETCH completed.\r\n')
        self.transport.push_logout()
        await self.run()

    async def test_append_user_not_found(self):
        handlers = GrpcHandlers(self.backend)
        request = AppendRequest(user='baduser')
        stream = _Stream(request)
        await handlers.Append(stream)
        response: AppendResponse = stream.response
        assert USER_NOT_FOUND == response.result

    async def test_append_mailbox_not_found(self):
        handlers = GrpcHandlers(self.backend)
        request = AppendRequest(user='testuser', mailbox='BAD')
        stream = _Stream(request)
        await handlers.Append(stream)
        response: AppendResponse = stream.response
        assert MAILBOX_NOT_FOUND == response.result


class TestAdminClient:

    async def test_append(self):
        parser = ArgumentParser()
        subparsers = parser.add_subparsers(dest='test')
        name, command = AppendCommand.init(parser, subparsers)
        stub = _Stub('append response')
        args = Namespace(user='testuser', mailbox='INBOX',
                         data=BytesIO(b'test data'),
                         flags=['\\Flagged', '\\Seen'],
                         timestamp=1234567890.0)
        response = await command.run(stub, args)
        request = stub.request
        assert 'Append' == stub.method
        assert 'append response' == response
        assert b'test data' == request.data
        assert 1234567890.0 == request.when
        assert ['\\Flagged', '\\Seen'] == request.flags
        assert 'testuser' == request.user
        assert 'INBOX' == request.mailbox
