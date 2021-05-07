
from __future__ import annotations

import asyncio
import binascii
import logging
import re
from argparse import ArgumentParser
from asyncio import StreamReader, StreamWriter
from base64 import b64encode, b64decode
from collections.abc import Mapping
from contextlib import closing, AsyncExitStack
from typing import Optional, Union

from proxyprotocol import ProxyProtocolResult
from proxyprotocol.reader import ProxyProtocolReader
from proxyprotocol.sock import SocketInfo
from pymap import __version__
from pymap.bytes import BytesFormat
from pymap.config import IMAPConfig
from pymap.context import socket_info, language_code, connection_exit
from pymap.exceptions import InvalidAuth
from pymap.interfaces.backend import ServiceInterface
from pymap.interfaces.login import LoginInterface
from pymap.interfaces.session import SessionInterface
from pymap.parsing.exceptions import NotParseable
from pymap.parsing.primitives import String
from pysasl import ServerChallenge, ChallengeResponse, AuthenticationError, \
    AuthenticationCredentials

from .command import Command, NoOpCommand, LogoutCommand, CapabilityCommand, \
    AuthenticateCommand, UnauthenticateCommand, StartTLSCommand
from .response import Condition, Response, BadCommandResponse, NoOpResponse, \
    CapabilitiesResponse
from .state import FilterState
from .. import SieveCompiler

__all__ = ['ManageSieveService', 'ManageSieveServer', 'ManageSieveConnection']

_log = logging.getLogger(__name__)


class ManageSieveService(ServiceInterface):  # pragma: no cover
    """A pymap service that implements a ManageSieve server to control the
    sieve scripts associated with a login.

    See Also:
        `RFC 5804 <https://tools.ietf.org/html/rfc5804>`_,
        :class:`~pymap.interfaces.filter.FilterSetInterface`

    """

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        group = parser.add_argument_group('managesieve service')
        group.add_argument('--sieve-host', action='append', metavar='IFACE',
                           help='the network interface to listen on')
        group.add_argument('--sieve-port',  metavar='NUM', default='4190',
                           help='the port or service name to listen on')

    async def start(self, stack: AsyncExitStack) -> None:
        backend = self.backend
        config = self.config
        managesieve_server = ManageSieveServer(backend.login, config)
        host: Optional[str] = config.args.sieve_host
        port: Union[str, int] = config.args.sieve_port
        server = await asyncio.start_server(
            managesieve_server, host=host, port=port)
        await stack.enter_async_context(server)
        task = asyncio.create_task(server.serve_forever())
        stack.callback(task.cancel)


class ManageSieveServer:
    """Callable object that creates and runs :class:`ManageSieveConnection`
    objects when :func:`asyncio.start_server` receives a new connection.

    Args:
        login: Login callback that takes authentication credentials and returns
            a :class:`~pymap.interfaces.session.SessionInterface` object.
        config: Settings to use for the sieve server.

    """

    def __init__(self, login: LoginInterface, config: IMAPConfig) -> None:
        super().__init__()
        self._login = login
        self._config = config

    async def __call__(self, reader: StreamReader,
                       writer: StreamWriter) -> None:
        conn = ManageSieveConnection(self._login, self._config, reader, writer)
        async with AsyncExitStack() as stack:
            connection_exit.set(stack)
            stack.enter_context(closing(writer))
            await conn.run()


class ManageSieveConnection:
    """Runs a single ManageSieve connection from start to finish.

    Args:
        login: Login callback that takes authentication credentials and returns
            a :class:`~pymap.interfaces.session.SessionInterface` object.
        config: Settings to use for the sieve server.
        reader: The input stream for the socket.
        writer: The output stream for the socket.

    """

    _lines = re.compile(r'\r?\n')
    _literal_plus = re.compile(br'{(\d+)\+}\r?\n$')
    _impl = b'pymap managesieve ' + __version__.encode('ascii')

    def __init__(self, login: LoginInterface, config: IMAPConfig,
                 reader: StreamReader, writer: StreamWriter) -> None:
        super().__init__()
        self.login = login
        self.config = config
        self.auth = config.initial_auth
        self.params = config.parsing_params.copy(allow_continuations=False)
        self.pp_reader = ProxyProtocolReader(config.proxy_protocol)
        self.pp_result: Optional[ProxyProtocolResult] = None
        self._offer_starttls = b'STARTTLS' in config.initial_capability
        self._state: Optional[FilterState] = None
        self._reset_streams(reader, writer)

    def _reset_streams(self, reader: StreamReader,
                       writer: StreamWriter) -> None:
        self.reader = reader
        self.writer = writer
        socket_info.set(SocketInfo(writer, self.pp_result))

    async def _read_proxy_protocol(self) -> None:
        self.pp_result = await self.pp_reader.read(self.reader)
        self._reset_streams(self.reader, self.writer)

    def _get_state(self, session: SessionInterface) -> FilterState:
        owner = session.owner.encode('utf-8')
        if session.filter_set is None:
            raise ValueError('Filters not supported.')
        return FilterState(session.filter_set, owner, self.config)

    @property
    def capabilities(self) -> Mapping[bytes, Optional[bytes]]:
        ret: dict[bytes, Optional[bytes]] = {}
        ret[b'IMPLEMENTATION'] = self._impl
        if self._state is None:
            ret[b'SASL'] = b' '.join(
                mech.name for mech in self.auth.server_mechanisms)
        ret[b'SIEVE'] = b' '.join(SieveCompiler.extensions)
        if self._offer_starttls and self._state is None:
            ret[b'STARTTLS'] = None
        try:
            ret[b'LANGUAGE'] = language_code.get().encode('ascii')
        except LookupError:
            pass
        if self._state is not None:
            ret[b'OWNER'] = self._state.owner
        ret[b'UNAUTHENTICATE'] = None
        ret[b'VERSION'] = b'1.0'
        return ret

    @classmethod
    def _print(cls, log_format: str, output: Union[str, bytes]) -> None:
        if _log.isEnabledFor(logging.DEBUG):
            fd = socket_info.get().socket.fileno()
            if not isinstance(output, str):
                output = str(output, 'utf-8', 'replace')
            lines = cls._lines.split(output)
            if not lines[-1]:
                lines = lines[:-1]
            for line in lines:
                _log.debug(log_format, fd, line)

    async def _read_data(self) -> memoryview:
        data = bytearray()
        while True:
            data += await self.reader.readline()
            if not data.endswith(b'\n'):
                raise EOFError()
            match = self._literal_plus.search(data)
            if not match:
                break
            literal_length = int(match.group(1))
            data += await self.reader.readexactly(literal_length)
        self._print('%d -->| %s', data)
        return memoryview(data)

    async def _read_command(self) -> Command:
        cmd_buf = await self._read_data()
        cmd, _ = Command.parse(cmd_buf, self.params)
        return cmd

    async def _write_response(self, resp: Response) -> None:
        resp.write(self.writer)
        try:
            await self.writer.drain()
        except ConnectionError:
            pass
        else:
            self._print('%d <--| %s', bytes(resp))

    async def _login(self, creds: AuthenticationCredentials) \
            -> SessionInterface:
        stack = connection_exit.get()
        identity = await self.login.authenticate(creds)
        return await stack.enter_async_context(identity.new_session())

    async def _do_greeting(self) -> Response:
        preauth_creds = self.config.preauth_credentials
        if preauth_creds:
            session = await self._login(preauth_creds)
            try:
                self._state = self._get_state(session)
            except ValueError as exc:
                return Response(Condition.NO, text=str(exc))
        return CapabilitiesResponse(self.capabilities)

    async def _do_authenticate(self, cmd: AuthenticateCommand) -> Response:
        mech = self.auth.get_server(cmd.mech_name)
        if not mech:
            return Response(Condition.NO, text='Invalid SASL mechanism.')
        responses: list[ChallengeResponse] = []
        if cmd.initial_data is not None:
            resp_dec = b64decode(cmd.initial_data)
            responses.append(ChallengeResponse(b'', resp_dec))
        while True:
            try:
                creds, final = mech.server_attempt(responses)
            except ServerChallenge as chal:
                chal_bytes = b64encode(chal.data)
                chal_str = String.build(chal_bytes)
                chal_str.write(self.writer)
                self.writer.write(b'\r\n')
                await self.writer.drain()
                resp_bytes = await self._read_data()
                resp_str, _ = String.parse(resp_bytes, self.params)
                if resp_str.value == b'*':
                    raise AuthenticationError('Authentication cancelled.')
                try:
                    resp_dec = b64decode(resp_str.value)
                except binascii.Error as exc:
                    raise AuthenticationError() from exc
                else:
                    responses.append(ChallengeResponse(chal.data, resp_dec))
            except AuthenticationError as exc:
                return Response(Condition.NO, text=str(exc))
            else:
                break
        if final is None:
            code: Optional[bytes] = None
        else:
            code = BytesFormat(b'SASL %b') % String.build(final)
        try:
            session = await self._login(creds)
        except InvalidAuth as exc:
            return Response(Condition.NO, text=str(exc))
        try:
            self._state = self._get_state(session)
        except ValueError as exc:
            return Response(Condition.NO, text=str(exc))
        return Response(Condition.OK, code=code)

    async def _do_unauthenticate(self) -> Response:
        if self._state is None:
            return Response(Condition.NO, text='Not authenticated.')
        else:
            self._state = None
            return Response(Condition.OK)

    async def _do_starttls(self) -> Response:
        ssl_context = self.config.ssl_context
        if not self._offer_starttls:
            return Response(Condition.NO, text='Bad command.')
        resp = Response(Condition.OK)
        await self._write_response(resp)
        loop = asyncio.get_event_loop()
        transport = self.writer.transport
        protocol = transport.get_protocol()
        new_transport = await loop.start_tls(
            transport, protocol, ssl_context, server_side=True)
        new_protocol = new_transport.get_protocol()
        new_writer = StreamWriter(new_transport, new_protocol,
                                  self.reader, loop)
        self._reset_streams(self.reader, new_writer)
        self._print('%d <->| %s', b'<TLS handshake>')
        self._offer_starttls = False
        self.auth = self.config.tls_auth
        return CapabilitiesResponse(self.capabilities)

    async def run(self) -> None:
        """Start the socket communication with the server greeting, and then
        enter the command/response cycle.

        """
        await self._read_proxy_protocol()
        self._print('%d +++| %s', str(socket_info.get()))
        greeting = await self._do_greeting()
        await self._write_response(greeting)
        while True:
            resp: Response
            try:
                cmd = await self._read_command()
            except (ConnectionError, EOFError):
                break
            except NotParseable as exc:
                resp = BadCommandResponse(exc)
            else:
                try:
                    if isinstance(cmd, NoOpCommand):
                        resp = NoOpResponse(cmd.tag)
                    elif isinstance(cmd, LogoutCommand):
                        resp = Response(Condition.BYE)
                    elif isinstance(cmd, CapabilityCommand):
                        resp = CapabilitiesResponse(self.capabilities)
                    elif self._state is None:
                        if isinstance(cmd, AuthenticateCommand):
                            resp = await self._do_authenticate(cmd)
                        elif isinstance(cmd, StartTLSCommand):
                            resp = await self._do_starttls()
                        else:
                            resp = Response(Condition.NO, text='Bad command.')
                    else:
                        if isinstance(cmd, UnauthenticateCommand):
                            resp = await self._do_unauthenticate()
                        else:
                            resp = await self._state.run(cmd)
                except Exception:
                    _log.exception('Unhandled exception')
                    resp = Response(Condition.NO, text='Server error.')
            await self._write_response(resp)
            if resp.is_bye:
                break
        self._print('%d ---| %s', b'<disconnected>')
