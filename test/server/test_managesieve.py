
from .base import TestBase
from .mocktransport import MockTransport

from pymap.sieve.manage import ManageSieveServer


class TestManageSieve(TestBase):

    def _push_capabilities(self, transport: MockTransport) -> None:
        transport.push_write(
            b'"IMPLEMENTATION" "pymap managesieve', (br'.*?', ), b'"\r\n'
            b'"SASL" "PLAIN LOGIN"\r\n'
            b'"SIEVE" "fileinto reject envelope body"\r\n'
            b'"UNAUTHENTICATE"\r\n'
            b'"VERSION" "1.0"\r\n'
            b'OK\r\n')

    def _push_logout(self, transport: MockTransport) -> None:
        transport.push_readline(
            b'logout\r\n')
        transport.push_write(
            b'BYE\r\n')

    def _push_authenticate(self, transport: MockTransport) -> None:
        transport.push_readline(
            b'authenticate "plain"\r\n')
        transport.push_write(
            b'""\r\n')
        transport.push_readline(
            b'{24+}\r\n'
            b'AHRlc3R1c2VyAHRlc3RwYXNz\r\n')
        transport.push_write(
            b'OK\r\n')

    async def test_capabilities(
            self, managesieve_server: ManageSieveServer) -> None:
        transport = self.new_transport(managesieve_server)
        self._push_capabilities(transport)
        self._push_logout(transport)
        await self.run(transport)

    async def test_authenticate(
            self, managesieve_server: ManageSieveServer) -> None:
        transport = self.new_transport(managesieve_server)
        self._push_capabilities(transport)
        self._push_authenticate(transport)
        self._push_logout(transport)
        await self.run(transport)

    async def test_capability(
            self, managesieve_server: ManageSieveServer) -> None:
        transport = self.new_transport(managesieve_server)
        self._push_capabilities(transport)
        transport.push_readline(
            b'capability\r\n')
        self._push_capabilities(transport)
        self._push_authenticate(transport)
        transport.push_readline(
            b'capability\r\n')
        transport.push_write(
            b'"IMPLEMENTATION" "pymap managesieve', (br'.*?', ), b'"\r\n'
            b'"SIEVE" "fileinto reject envelope body"\r\n'
            b'"OWNER" "testuser"\r\n'
            b'"UNAUTHENTICATE"\r\n'
            b'"VERSION" "1.0"\r\n'
            b'OK\r\n')
        self._push_logout(transport)
        await self.run(transport)

    async def test_unauthenticate(
            self, managesieve_server: ManageSieveServer) -> None:
        transport = self.new_transport(managesieve_server)
        self._push_capabilities(transport)
        self._push_authenticate(transport)
        transport.push_readline(
            b'unauthenticate\r\n')
        transport.push_write(
            b'OK\r\n')
        transport.push_readline(
            b'capability\r\n')
        self._push_capabilities(transport)
        self._push_logout(transport)
        await self.run(transport)

    async def test_bad_command(
            self, managesieve_server: ManageSieveServer) -> None:
        transport = self.new_transport(managesieve_server)
        self._push_capabilities(transport)
        transport.push_readline(
            b'bad\r\n')
        transport.push_write(
            b'NO "Bad command: [:ERROR:]bad"\r\n')
        self._push_authenticate(transport)
        transport.push_readline(
            b'bad again\r\n')
        transport.push_write(
            b'NO "Bad command: [:ERROR:]bad again"\r\n')
        self._push_logout(transport)
        await self.run(transport)

    async def test_listscripts(
            self, managesieve_server: ManageSieveServer) -> None:
        transport = self.new_transport(managesieve_server)
        self._push_capabilities(transport)
        self._push_authenticate(transport)
        transport.push_readline(
            b'listscripts\r\n')
        transport.push_write(
            b'"demo" ACTIVE\r\n'
            b'OK\r\n')
        self._push_logout(transport)
        await self.run(transport)

    async def test_getscript(
            self, managesieve_server: ManageSieveServer) -> None:
        transport = self.new_transport(managesieve_server)
        self._push_capabilities(transport)
        self._push_authenticate(transport)
        transport.push_readline(
            b'getscript "demo"\r\n')
        transport.push_write(
            b'{937}\r\nrequire ["fileinto", "envelope", "reject"];\n\n'
            b'if header :is "Subject" "reject this" {\n    '
            b'reject "message rejected";\n}\n\n'
            b'if header :is "Subject" "discard this" {\n    '
            b'discard;\n}\n\n'
            b'if address :is :all "from" "foo@example.com" {\n    '
            b'fileinto "Test 1";\n}\n\n'
            b'if address :contains :domain "from" "foo" {\n    '
            b'fileinto "Test 2";\n}\n\n'
            b'if address :matches :localpart "to" "*foo?" {\n    '
            b'fileinto "Test 3";\n}\n\n'
            b'if envelope :is :all "from" "foo@example.com" {\n    '
            b'fileinto "Test 4";\n}\n\n'
            b'if envelope :contains :domain "from" "foo" {\n    '
            b'fileinto "Test 5";\n}\n\n'
            b'if envelope :matches :localpart "to" "*foo?" {\n    '
            b'fileinto "Test 6";\n}\n\n'
            b'if exists ["X-Foo", "X-Bar"] {\n    '
            b'fileinto "Test 7";\n}\n\n'
            b'if header :is ["X-Caffeine"] ["C8H10N4O2"] {\n    '
            b'fileinto "Test 8";\n}\n\n'
            b'if allof(not size :under 1234, not size :over 1234) {\n    '
            b'fileinto "Test 9";\n}\n\n'
            b'if allof (true, false) {\n    discard;\n} '
            b'elsif false {\n    discard;\n} '
            b'elsif not true {\n    discard;\n} '
            b'else {\n    keep;\n}\n\r\n'
            b'OK\r\n')
        self._push_logout(transport)
        await self.run(transport)

    async def test_havespace(
            self, managesieve_server: ManageSieveServer) -> None:
        transport = self.new_transport(managesieve_server)
        self._push_capabilities(transport)
        self._push_authenticate(transport)
        transport.push_readline(
            b'havespace "demo" 1234\r\n')
        transport.push_write(
            b'OK\r\n')
        self._push_logout(transport)
        await self.run(transport)

    async def test_putscript(
            self, managesieve_server: ManageSieveServer) -> None:
        transport = self.new_transport(managesieve_server)
        self._push_capabilities(transport)
        self._push_authenticate(transport)
        transport.push_readline(
            b'putscript "test" {10+}\r\n'
            b'discard;\r\n\r\n')
        transport.push_write(
            b'OK\r\n')
        transport.push_readline(
            b'setactive "test"\r\n')
        transport.push_write(
            b'OK\r\n')
        transport.push_readline(
            b'listscripts\r\n')
        transport.push_write(
            b'"demo"\r\n'
            b'"test" ACTIVE\r\n'
            b'OK\r\n')
        self._push_logout(transport)
        await self.run(transport)

    async def test_deletescript(
            self, managesieve_server: ManageSieveServer) -> None:
        transport = self.new_transport(managesieve_server)
        self._push_capabilities(transport)
        self._push_authenticate(transport)
        transport.push_readline(
            b'deletescript "demo"\r\n')
        transport.push_write(
            b'NO (ACTIVE)\r\n')
        transport.push_readline(
            b'setactive ""\r\n')
        transport.push_write(
            b'OK\r\n')
        transport.push_readline(
            b'deletescript "demo"\r\n')
        transport.push_write(
            b'OK\r\n')
        transport.push_readline(
            b'listscripts\r\n')
        transport.push_write(
            b'OK\r\n')
        self._push_logout(transport)
        await self.run(transport)

    async def test_renamescript(
            self, managesieve_server: ManageSieveServer) -> None:
        transport = self.new_transport(managesieve_server)
        self._push_capabilities(transport)
        self._push_authenticate(transport)
        transport.push_readline(
            b'renamescript "demo" "test"\r\n')
        transport.push_write(
            b'OK\r\n')
        transport.push_readline(
            b'listscripts\r\n')
        transport.push_write(
            b'"test" ACTIVE\r\n'
            b'OK\r\n')
        self._push_logout(transport)
        await self.run(transport)

    async def test_checkscript(
            self, managesieve_server: ManageSieveServer) -> None:
        transport = self.new_transport(managesieve_server)
        self._push_capabilities(transport)
        self._push_authenticate(transport)
        transport.push_readline(
            b'checkscript {10+}\r\n'
            b'discard;\r\n\r\n')
        transport.push_write(
            b'OK\r\n')
        transport.push_readline(
            b'checkscript {10+}\r\n'
            b'1234567890\r\n')
        transport.push_write(
            b'NO {67}\r\nline 1: parsing error: unexpected token '
            b"'1234567890' found near '1'\r\n")
        transport.push_readline(
            b'checkscript {19+}\r\n'
            b'else { discard; }\r\n\r\n')
        transport.push_write(
            b'NO {74}\r\n'
            b'line 1: parsing error: the else command must follow an '
            b'if or elsif command\r\n')
        self._push_logout(transport)
        await self.run(transport)
