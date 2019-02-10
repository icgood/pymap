
import asyncio
import logging
import re
from argparse import ArgumentParser
from asyncio import Task, StreamReader, StreamWriter, AbstractServer
from base64 import b64encode, b64decode
from collections import OrderedDict
from typing import Optional, Union, Mapping, Dict, List

from pymap import __version__
from pymap.bytes import BytesFormat
from pymap.config import IMAPConfig
from pymap.context import socket_info, language_code
from pymap.exceptions import InvalidAuth
from pymap.interfaces.backend import BackendInterface, ServiceInterface
from pymap.interfaces.session import LoginProtocol, SessionInterface
from pymap.parsing.exceptions import NotParseable
from pymap.parsing.primitives import String
from pymap.sockinfo import SocketInfo
from pysasl import ServerChallenge, AuthenticationError

from .command import Command, NoOpCommand, LogoutCommand, CapabilityCommand, \
    AuthenticateCommand, UnauthenticateCommand, StartTLSCommand
from .response import Condition, Response, BadCommandResponse, NoOpResponse, \
    CapabilitiesResponse
from .state import FilterState

__all__ = ['ManageSieveService', 'ManageSieveServer', 'ManageSieveConnection']

_log = logging.getLogger(__name__)


class ManageSieveService(ServiceInterface):
    """A pymap service that implements a ManageSieve server to control the
    sieve scripts associated with a login.

    See Also:
        `RFC 5804 <https://tools.ietf.org/html/rfc5804>`_,
        :class:`~pymap.interfaces.filter.FilterSetInterface`

    """

    def __init__(self, server: AbstractServer) -> None:
        super().__init__()
        self._server = server
        self._task = asyncio.create_task(self._run())

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        group = parser.add_argument_group('managesieve service')
        group.add_argument('--sieve-host', action='append', metavar='IFACE',
                           help='the network interface to listen on')
        group.add_argument('--sieve-port',  metavar='NUM', default='sieve',
                           help='the port or service name to listen on')

    @classmethod
    async def start(cls, backend: BackendInterface,
                    config: IMAPConfig) -> 'ManageSieveService':
        managesieve_server = ManageSieveServer(backend.login, backend.config)
        host: Optional[str] = config.args.sieve_host
        port: Union[str, int] = config.args.sieve_port
        server = await asyncio.start_server(
            managesieve_server, host=host, port=port)
        return cls(server)

    @property
    def task(self) -> Task:
        return self._task

    async def _run(self) -> None:
        async with self._server:  # type: ignore
            await self._server.serve_forever()  # type: ignore


class ManageSieveServer:
    """Callable object that creates and runs :class:`ManageSieveConnection`
    objects when :func:`asyncio.start_server` receives a new connection.

    Args:
        login: Login callback that takes authentication credentials and returns
            a :class:`~pymap.interfaces.session.SessionInterface` object.

    """

    def __init__(self, login: LoginProtocol, config: IMAPConfig) -> None:
        super().__init__()
        self._login = login
        self._config = config

    async def __call__(self, reader: StreamReader,
                       writer: StreamWriter) -> None:
        conn = ManageSieveConnection(self._config, reader, writer)
        try:
            await conn.run(self._login)
        finally:
            writer.close()


class ManageSieveConnection:
    """Runs a single ManageSieve connection from start to finish.

    Args:
        reader: The input stream for the socket.
        writer: The output stream for the socket.

    """

    _lines = re.compile(br'\r?\n')
    _literal_plus = re.compile(br'{(\d+)\+}\r?\n$')
    _impl = b'pymap managesieve ' + __version__.encode('ascii')

    def __init__(self, config: IMAPConfig, reader: StreamReader,
                 writer: StreamWriter) -> None:
        super().__init__()
        self.config = config
        self.auth = config.initial_auth
        self.params = config.parsing_params.copy(allow_continuations=False)
        self._offer_starttls = b'STARTTLS' in config.initial_capability
        self._session: Optional[SessionInterface] = None
        self._reset_streams(reader, writer)

    def _reset_streams(self, reader: StreamReader,
                       writer: StreamWriter) -> None:
        self.reader = reader
        self.writer = writer
        socket_info.set(SocketInfo(writer))

    @property
    def capabilities(self) -> Mapping[bytes, Optional[bytes]]:
        ret: Dict[bytes, Optional[bytes]] = OrderedDict()
        ret[b'IMPLEMENTATION'] = self._impl
        if self._session is None:
            ret[b'SASL'] = b' '.join(
                mech.name for mech in self.auth.server_mechanisms)
        ret[b'SIEVE'] = b''
        if self._offer_starttls and self._session is None:
            ret[b'STARTTLS'] = None
        try:
            ret[b'LANGUAGE'] = language_code.get().encode('ascii')
        except LookupError:
            pass
        if self._session is not None:
            ret[b'OWNER'] = self._session.owner.encode('utf-8')
        ret[b'UNAUTHENTICATE'] = None
        ret[b'VERSION'] = b'1.0'
        return ret

    @classmethod
    def _print(cls, log_format: str, output: bytes) -> None:
        if _log.isEnabledFor(logging.DEBUG):
            fd = socket_info.get().socket.fileno()
            lines = cls._lines.split(output)
            if not lines[-1]:
                lines = lines[:-1]
            for line in lines:
                line_str = str(line, 'utf-8', 'replace')
                _log.debug(log_format, fd, line_str)

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

    async def _do_greeting(self, login: LoginProtocol) -> None:
        preauth_creds = self.config.preauth_credentials
        if preauth_creds:
            self._session = await login(preauth_creds, self.config)
        greeting = CapabilitiesResponse(self.capabilities)
        await self._write_response(greeting)

    async def _do_authenticate(self, login: LoginProtocol,
                               cmd: AuthenticateCommand) -> Response:
        mech = self.auth.get_server(cmd.mech_name)
        if not mech:
            return Response(Condition.NO, text='Invalid SASL mechanism.')
        responses: List[ServerChallenge] = []
        if cmd.initial_data is not None:
            chal = ServerChallenge(b'')
            chal.set_response(b64decode(cmd.initial_data))
            responses.append(chal)
        while True:
            try:
                creds, final = mech.server_attempt(responses)
            except ServerChallenge as chal:
                chal_bytes = b64encode(chal.get_challenge())
                chal_str = String.build(chal_bytes)
                chal_str.write(self.writer)
                self.writer.write(b'\r\n')
                await self.writer.drain()
                resp_bytes = await self._read_data()
                resp_str, _ = String.parse(resp_bytes, self.params)
                chal.set_response(b64decode(resp_str.value))
                if resp_str.value == b'*':
                    raise AuthenticationError('Authentication cancelled.')
                responses.append(chal)
            except AuthenticationError as exc:
                return Response(Condition.NO, text=str(exc))
            else:
                break
        if final is None:
            code: Optional[bytes] = None
        else:
            code = BytesFormat(b'SASL %b') % String.build(final)
        try:
            session = await login(creds, self.config)
        except InvalidAuth as exc:
            return Response(Condition.NO, text=str(exc))
        else:
            if session.filter_set is None:
                return Response(Condition.NO, text='Filters not supported.')
            self._session = session
            return Response(Condition.OK, code=code)

    async def _do_unauthenticate(self) -> Response:
        if self._session is None:
            return Response(Condition.NO, text='Not authenticated.')
        else:
            self._session = None
            return Response(Condition.OK)

    async def _do_starttls(self) -> Response:
        ssl_context = self.config.ssl_context
        if ssl_context is None:
            raise ValueError('ssl_context is None')
        elif not self._offer_starttls:
            return Response(Condition.NO, text='Bad command.')
        resp = Response(Condition.OK)
        await self._write_response(resp)
        loop = asyncio.get_event_loop()
        transport = self.writer.transport
        protocol = transport.get_protocol()  # type: ignore
        new_transport = await loop.start_tls(  # type: ignore
            transport, protocol, ssl_context, server_side=True)
        protocol._stream_reader = StreamReader(loop=loop)
        protocol._client_connected_cb = self._reset_streams
        protocol.connection_made(new_transport)
        self._print('%d <->| %s', b'<TLS handshake>')
        self._offer_starttls = False
        return CapabilitiesResponse(self.capabilities)

    async def run(self, login: LoginProtocol):
        """Start the socket communication with the server greeting, and then
        enter the command/response cycle.

        Args:
            login: The login/authentication function.

        """
        self._print('%d +++| %s', bytes(socket_info.get()))
        await self._do_greeting(login)
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
                    elif self._session is None:
                        if isinstance(cmd, AuthenticateCommand):
                            resp = await self._do_authenticate(login, cmd)
                        elif isinstance(cmd, StartTLSCommand):
                            resp = await self._do_starttls()
                        else:
                            resp = Response(Condition.NO, text='Bad command.')
                    else:
                        if isinstance(cmd, UnauthenticateCommand):
                            resp = await self._do_unauthenticate()
                        else:
                            assert self._session.filter_set is not None
                            state = FilterState(self._session.filter_set,
                                                self.config)
                            resp = await state.run(cmd)
                except Exception:
                    _log.exception('Unhandled exception')
                    resp = Response(Condition.NO, text='Server error.')
            await self._write_response(resp)
            if resp.is_bye:
                break
        self._print('%d ---| %s', b'<disconnected>')
