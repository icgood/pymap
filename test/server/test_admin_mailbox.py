
import pytest
from grpclib.testing import ChannelFor
from pymapadmin.grpc.admin_grpc import MailboxStub
from pymapadmin.grpc.admin_pb2 import AppendRequest, SUCCESS, FAILURE

from pymap.admin.handlers.mailbox import MailboxHandlers
from pymap.imap import IMAPServer
from pymap.interfaces.backend import BackendInterface

from .base import TestBase


class TestMailboxHandlers(TestBase):

    admin_token = 'MDAwZWxvY2F0aW9uIAowMDEwaWRlbnRpZmllciAKMDAxNWNpZCByb2xlI' \
        'D0gYWRtaW4KMDAyZnNpZ25hdHVyZSDND4TS4f6mH9ty0DHCwqB0IIuk_IqIUFgse0OV' \
        'eHT7cAo'
    metadata = {'auth-token': admin_token}

    @pytest.fixture
    def overrides(self):
        return {'admin_key': b'testadmintoken'}

    async def test_append(self, backend: BackendInterface,
                          imap_server: IMAPServer) -> None:
        handlers = MailboxHandlers(backend)
        data = b'From: user@example.com\n\ntest message!\n'
        request = AppendRequest(user='testuser', mailbox='INBOX',
                                flags=['\\Flagged', '\\Seen'],
                                when=1234567890, data=data)
        async with ChannelFor([handlers]) as channel:
            stub = MailboxStub(channel)
            response = await stub.Append(request, metadata=self.metadata)
        assert SUCCESS == response.result.code
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

    async def test_append_user_not_found(self, backend: BackendInterface) \
            -> None:
        handlers = MailboxHandlers(backend)
        request = AppendRequest(user='baduser')
        async with ChannelFor([handlers]) as channel:
            stub = MailboxStub(channel)
            response = await stub.Append(request, metadata=self.metadata)
        assert FAILURE == response.result.code
        assert 'UserNotFound' == response.result.key

    async def test_append_mailbox_not_found(self, backend: BackendInterface) \
            -> None:
        handlers = MailboxHandlers(backend)
        request = AppendRequest(user='testuser', mailbox='BAD')
        async with ChannelFor([handlers]) as channel:
            stub = MailboxStub(channel)
            response = await stub.Append(request, metadata=self.metadata)
        assert FAILURE == response.result.code
        assert 'BAD' == response.mailbox
        assert 'MailboxNotFound' == response.result.key

    async def test_append_filter_reject(self, backend: BackendInterface) \
            -> None:
        handlers = MailboxHandlers(backend)
        data = b'Subject: reject this\n\ntest message!\n'
        request = AppendRequest(user='testuser', mailbox='INBOX',
                                flags=['\\Flagged', '\\Seen'],
                                when=1234567890, data=data)
        async with ChannelFor([handlers]) as channel:
            stub = MailboxStub(channel)
            response = await stub.Append(request, metadata=self.metadata)
        assert FAILURE == response.result.code
        assert 'AppendFailure' == response.result.key

    async def test_append_filter_discard(self, backend: BackendInterface) \
            -> None:
        handlers = MailboxHandlers(backend)
        data = b'Subject: discard this\n\ntest message!\n'
        request = AppendRequest(user='testuser', mailbox='INBOX',
                                flags=['\\Flagged', '\\Seen'],
                                when=1234567890, data=data)
        async with ChannelFor([handlers]) as channel:
            stub = MailboxStub(channel)
            response = await stub.Append(request, metadata=self.metadata)
        assert SUCCESS == response.result.code
        assert not response.mailbox
        assert not response.uid

    async def test_append_filter_address_is(self, backend: BackendInterface) \
            -> None:
        handlers = MailboxHandlers(backend)
        data = b'From: foo@example.com\n\ntest message!\n'
        request = AppendRequest(user='testuser', mailbox='INBOX',
                                flags=['\\Flagged', '\\Seen'],
                                when=1234567890, data=data)
        async with ChannelFor([handlers]) as channel:
            stub = MailboxStub(channel)
            response = await stub.Append(request, metadata=self.metadata)
        assert 'Test 1' == response.mailbox

    async def test_append_filter_address_contains(
            self, backend: BackendInterface) -> None:
        handlers = MailboxHandlers(backend)
        data = b'From: user@foo.com\n\ntest message!\n'
        request = AppendRequest(user='testuser', mailbox='INBOX',
                                flags=['\\Flagged', '\\Seen'],
                                when=1234567890, data=data)
        async with ChannelFor([handlers]) as channel:
            stub = MailboxStub(channel)
            response = await stub.Append(request, metadata=self.metadata)
        assert 'Test 2' == response.mailbox

    async def test_append_filter_address_matches(
            self, backend: BackendInterface) -> None:
        handlers = MailboxHandlers(backend)
        data = b'To: bigfoot@example.com\n\ntest message!\n'
        request = AppendRequest(user='testuser', mailbox='INBOX',
                                flags=['\\Flagged', '\\Seen'],
                                when=1234567890, data=data)
        async with ChannelFor([handlers]) as channel:
            stub = MailboxStub(channel)
            response = await stub.Append(request, metadata=self.metadata)
        assert 'Test 3' == response.mailbox

    async def test_append_filter_envelope_is(
            self, backend: BackendInterface) -> None:
        handlers = MailboxHandlers(backend)
        data = b'From: user@example.com\n\ntest message!\n'
        request = AppendRequest(user='testuser', mailbox='INBOX',
                                sender='foo@example.com',
                                flags=['\\Flagged', '\\Seen'],
                                when=1234567890, data=data)
        async with ChannelFor([handlers]) as channel:
            stub = MailboxStub(channel)
            response = await stub.Append(request, metadata=self.metadata)
        assert 'Test 4' == response.mailbox

    async def test_append_filter_envelope_contains(
            self, backend: BackendInterface) -> None:
        handlers = MailboxHandlers(backend)
        data = b'From: user@example.com\n\ntest message!\n'
        request = AppendRequest(user='testuser', mailbox='INBOX',
                                sender='user@foo.com',
                                flags=['\\Flagged', '\\Seen'],
                                when=1234567890, data=data)
        async with ChannelFor([handlers]) as channel:
            stub = MailboxStub(channel)
            response = await stub.Append(request, metadata=self.metadata)
        assert 'Test 5' == response.mailbox

    async def test_append_filter_envelope_matches(
            self, backend: BackendInterface) -> None:
        handlers = MailboxHandlers(backend)
        data = b'From: user@example.com\n\ntest message!\n'
        request = AppendRequest(user='testuser', mailbox='INBOX',
                                recipient='bigfoot@example.com',
                                flags=['\\Flagged', '\\Seen'],
                                when=1234567890, data=data)
        async with ChannelFor([handlers]) as channel:
            stub = MailboxStub(channel)
            response = await stub.Append(request, metadata=self.metadata)
        assert 'Test 6' == response.mailbox

    async def test_append_filter_exists(self, backend: BackendInterface) \
            -> None:
        handlers = MailboxHandlers(backend)
        data = b'X-Foo: foo\nX-Bar: bar\n\ntest message!\n'
        request = AppendRequest(user='testuser', mailbox='INBOX',
                                flags=['\\Flagged', '\\Seen'],
                                when=1234567890, data=data)
        async with ChannelFor([handlers]) as channel:
            stub = MailboxStub(channel)
            response = await stub.Append(request, metadata=self.metadata)
        assert 'Test 7' == response.mailbox

    async def test_append_filter_header(self, backend: BackendInterface) \
            -> None:
        handlers = MailboxHandlers(backend)
        data = b'X-Caffeine: C8H10N4O2\n\ntest message!\n'
        request = AppendRequest(user='testuser', mailbox='INBOX',
                                flags=['\\Flagged', '\\Seen'],
                                when=1234567890, data=data)
        async with ChannelFor([handlers]) as channel:
            stub = MailboxStub(channel)
            response = await stub.Append(request, metadata=self.metadata)
        assert 'Test 8' == response.mailbox

    async def test_append_filter_size(self, backend: BackendInterface) -> None:
        handlers = MailboxHandlers(backend)
        data = b'From: user@example.com\n\ntest message!\n'
        data = data + b'x' * (1234 - len(data))
        request = AppendRequest(user='testuser', mailbox='INBOX',
                                flags=['\\Flagged', '\\Seen'],
                                when=1234567890, data=data)
        async with ChannelFor([handlers]) as channel:
            stub = MailboxStub(channel)
            response = await stub.Append(request, metadata=self.metadata)
        assert 'Test 9' == response.mailbox
