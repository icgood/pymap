
from __future__ import annotations

import asyncio
import binascii
import logging
import re
import sys
from argparse import ArgumentParser
from asyncio import shield, StreamReader, StreamWriter, AbstractServer, \
    CancelledError, TimeoutError
from base64 import b64encode, b64decode
from collections.abc import Awaitable, Iterable
from contextlib import closing, AsyncExitStack
from typing import TypeVar, Union, Optional
from uuid import uuid4

from proxyprotocol import ProxyProtocolResult
from proxyprotocol.reader import ProxyProtocolReader
from proxyprotocol.sock import SocketInfo
from proxyprotocol.version import ProxyProtocolVersion
from pymap.concurrent import Event
from pymap.config import IMAPConfig
from pymap.context import subsystem, current_command, socket_info, \
    connection_exit
from pymap.exceptions import ResponseError
from pymap.interfaces.backend import ServiceInterface
from pymap.interfaces.login import LoginInterface
from pymap.parsing.command import Command
from pymap.parsing.commands import Commands
from pymap.parsing.command.nonauth import AuthenticateCommand, StartTLSCommand
from pymap.parsing.command.select import IdleCommand
from pymap.parsing.response import ResponseContinuation, Response, \
    ResponseCode, ResponseBad, ResponseNo, ResponseBye, ResponseOk, \
    CommandResponse
from pymap.parsing.state import ParsingState, ParsingInterrupt, \
    ExpectContinuation
from pymap.sockets import InheritedSockets
from pysasl import ServerChallenge, ChallengeResponse, AuthenticationError, \
    AuthenticationCredentials

from .state import ConnectionState

__all__ = ['IMAPService', 'IMAPServer', 'IMAPConnection']

_Ret = TypeVar('_Ret')
_log = logging.getLogger(__name__)


class IMAPService(ServiceInterface):  # pragma: no cover
    """A pymap service implementing an IMAP server."""

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        group = parser.add_argument_group('imap service')
        group.add_argument('--host', metavar='IFACE', action='append',
                           help='the network interface to listen on')
        group.add_argument('--port', metavar='NUM', default='143',
                           help='the port or service name to listen on')
        group.add_argument('--cert', metavar='FILE', help='cert file for TLS')
        group.add_argument('--key', metavar='FILE', help='key file for TLS')
        if InheritedSockets.supports('systemd'):
            group.add_argument('--systemd-sockets', action='store_const',
                               dest='inherited_sockets', const='systemd',
                               help='use systemd inherited sockets')
        else:
            parser.set_defaults(inherited_sockets=None)
        group.add_argument('--no-tls', dest='tls', action='store_false',
                           help='disable TLS')
        pp_choices = [v.name.lower() for v in ProxyProtocolVersion]
        group.add_argument('--proxy-protocol', choices=pp_choices,
                           help='the PROXY protocol version string')

    async def start(self, stack: AsyncExitStack) -> None:
        backend = self.backend
        config = self.config
        servers: list[AbstractServer] = []
        imap_server = IMAPServer(backend.login, config)
        if config.args.inherited_sockets:
            sockets = InheritedSockets.of(config.args.inherited_sockets).get()
            if not sockets:
                raise ValueError('No inherited sockets found')
            for sock in sockets:
                server = await asyncio.start_server(imap_server, sock=sock)
                servers.append(server)
        else:
            server = await asyncio.start_server(
                imap_server, host=config.host, port=config.port)
            servers.append(server)
        for server in servers:
            await stack.enter_async_context(server)
            task = asyncio.create_task(server.serve_forever())
            stack.callback(task.cancel)


class IMAPServer:
    """Callable object that creates and runs :class:`IMAPConnection` objects
    when :func:`asyncio.start_server` receives a new connection.

    Args:
        login: Login callback that takes authentication credentials and returns
            a :class:`~pymap.interfaces.session.SessionInterface` object.
        config: Settings to use for the IMAP server.

    """

    __slots__ = ['commands', '_login', '_config']

    def __init__(self, login: LoginInterface, config: IMAPConfig) -> None:
        super().__init__()
        self.commands = config.commands
        self._login = login
        self._config = config

    async def __call__(self, reader: StreamReader,
                       writer: StreamWriter) -> None:
        conn = IMAPConnection(self.commands, self._config, reader, writer)
        state = ConnectionState(self._login, self._config)
        async with AsyncExitStack() as stack:
            connection_exit.set(stack)
            stack.enter_context(closing(conn))
            await conn.run(state)


class IMAPConnection:
    """Runs a single IMAP connection from start to finish.

    Args:
        commands: Defines the IMAP commands available to the connection.
        config: Settings to use for the IMAP connection.
        reader: The input stream for the socket.
        writer: The output stream for the socket.

    """

    _lines = re.compile(r'\r?\n')
    _literal_plus = re.compile(br'{(\d+)\+}\r?\n$')

    __slots__ = ['commands', 'config', 'params', 'bad_command_limit',
                 'reader', 'writer', 'pp_reader', 'pp_result']

    def __init__(self, commands: Commands, config: IMAPConfig,
                 reader: StreamReader,
                 writer: StreamWriter) -> None:
        super().__init__()
        self.commands = commands
        self.config = config
        self.params = config.parsing_params
        self.bad_command_limit = config.bad_command_limit
        self.pp_reader = ProxyProtocolReader(config.proxy_protocol)
        self.pp_result: Optional[ProxyProtocolResult] = None
        self._reset_streams(reader, writer)

    def _reset_streams(self, reader: StreamReader,
                       writer: StreamWriter) -> None:
        self.reader = reader
        self.writer = writer
        socket_info.set(SocketInfo(writer, self.pp_result,
                                   unique_id=uuid4().bytes))

    async def _read_proxy_protocol(self) -> None:
        self.pp_result = await self.pp_reader.read(self.reader)
        self._reset_streams(self.reader, self.writer)

    def close(self) -> None:
        self.writer.close()

    @classmethod
    def _print(cls, log_format: str, output: Union[str, bytes]) -> None:
        if _log.isEnabledFor(logging.DEBUG):
            uid = socket_info.get().unique_id.hex()
            if not isinstance(output, str):
                output = str(output, 'utf-8', 'replace')
            lines = cls._lines.split(output)
            if not lines[-1]:
                lines = lines[:-1]
            for line in lines:
                _log.debug(log_format, uid, line)

    def _exec(self, future: Awaitable[_Ret]) -> Awaitable[_Ret]:
        return subsystem.get().execute(future)

    async def readline(self) -> memoryview:
        buf = bytearray(await self.reader.readline())
        while True:
            if not buf.endswith(b'\n'):
                raise EOFError()
            elif buf.endswith(b'+}\n') or buf.endswith(b'+}\r\n'):
                lit_plus = self._literal_plus.search(buf)
            else:
                lit_plus = None
            if lit_plus:
                literal_length = int(lit_plus.group(1))
                buf += await self.reader.readexactly(literal_length)
                buf += await self.reader.readline()
            else:
                self._print('%s -->| %s', buf)
                return memoryview(buf)

    async def read_continuation(self, literal_length: int) -> memoryview:
        extra_literal = await self.reader.readexactly(literal_length)
        self._print('%s -->| %s', extra_literal)
        extra_line = await self.readline()
        extra = extra_literal + bytes(extra_line)
        return memoryview(extra)

    async def authenticate(self, state: ConnectionState, mech_name: bytes) \
            -> Optional[AuthenticationCredentials]:
        mech = state.auth.get_server(mech_name)
        if not mech:
            return None
        responses: list[ChallengeResponse] = []
        while True:
            try:
                creds, final = mech.server_attempt(responses)
            except ServerChallenge as chal:
                chal_bytes = b64encode(chal.data)
                cont = ResponseContinuation(chal_bytes)
                await self.write_response(cont)
                resp_bytes = bytes(await self.read_continuation(0))
                if resp_bytes.rstrip(b'\r\n') == b'*':
                    raise AuthenticationError('Authentication canceled.')
                try:
                    resp_dec = b64decode(resp_bytes)
                except binascii.Error as exc:
                    raise AuthenticationError() from exc
                else:
                    responses.append(ChallengeResponse(chal.data, resp_dec))
            else:
                if final is not None:
                    cont = ResponseContinuation(b64encode(final))
                    await self.write_response(cont)
                    await self.read_continuation(0)
                return creds

    async def _interrupt(self, state: ConnectionState,
                         interrupt: ParsingInterrupt,
                         continuations: list[memoryview]) -> None:
        expected = interrupt.expected
        if isinstance(expected, ExpectContinuation):
            cont = ResponseContinuation(expected.message)
            await self.write_response(cont)
            ret = await self.read_continuation(expected.literal_length)
            continuations.append(ret)
        else:
            raise TypeError(expected) from interrupt

    async def read_command(self, state: ConnectionState) -> Command:
        line = await self.readline()
        conts: list[memoryview] = []
        while True:
            parsing_state = ParsingState(continuations=conts)
            params = self.params.copy(parsing_state)
            try:
                cmd, _ = self.commands.parse(line, params)
            except ParsingInterrupt as interrupt:
                await self._interrupt(state, interrupt, conts)
            else:
                return cmd

    async def read_idle_done(self, cmd: IdleCommand) -> bool:
        buf = await self.read_continuation(0)
        ok, _ = cmd.parse_done(buf)
        return ok

    async def write_response(self, resp: Response) -> None:
        await resp.async_write(self.writer)
        try:
            await self.writer.drain()
        except ConnectionError:
            pass
        else:
            self._print('%s <--| %s', bytes(resp))

    async def start_tls(self) -> None:
        loop = asyncio.get_event_loop()
        transport = self.writer.transport
        protocol = transport.get_protocol()
        ssl_context = self.config.ssl_context
        new_transport = await loop.start_tls(
            transport, protocol, ssl_context, server_side=True)
        new_protocol = new_transport.get_protocol()
        new_writer = StreamWriter(new_transport, new_protocol,
                                  self.reader, loop)
        self._reset_streams(self.reader, new_writer)
        self._print('%s <->| %s', b'<TLS handshake>')

    async def send_error_disconnect(self) -> None:
        _, exc, _ = sys.exc_info()
        if isinstance(exc, CancelledError):
            resp = ResponseBye(b'Server has closed the connection.',
                               ResponseCode.of(b'UNAVAILABLE'))
        else:
            resp = ResponseBye(b'Unhandled server error.',
                               ResponseCode.of(b'SERVERBUG'))
        try:
            await self.write_response(resp)
        except IOError:
            pass

    async def write_updates(self, untagged: Iterable[Response]) -> None:
        for i, resp in enumerate(untagged):
            await self.write_response(resp)

    async def handle_updates(self, state: ConnectionState, done: Event,
                             cmd: IdleCommand) -> None:
        while not done.is_set():
            untagged = await self._exec(state.receive_updates(cmd, done))
            await shield(self.write_updates(untagged))

    async def idle(self, state: ConnectionState, cmd: IdleCommand) \
            -> CommandResponse:
        response = await self._exec(state.do_command(cmd))
        if not isinstance(response, ResponseOk):
            return response
        await self.write_response(ResponseContinuation(b'Idling.'))
        done = subsystem.get().new_event()
        updates_task = asyncio.create_task(
            self.handle_updates(state, done, cmd))
        done_task = asyncio.create_task(self.read_idle_done(cmd))
        updates_exc: Optional[Exception] = None
        done_exc: Optional[Exception] = None
        try:
            ok = await done_task
        except Exception as exc:
            done_exc = exc
        finally:
            done.set()
        try:
            await updates_task
        except Exception as exc:
            updates_exc = exc
        if updates_exc:
            raise updates_exc
        elif done_exc:
            raise done_exc
        elif not ok:
            return ResponseBad(cmd.tag, b'Expected "DONE".')
        else:
            return response

    async def run(self, state: ConnectionState) -> None:
        """Start the socket communication with the IMAP greeting, and then
        enter the command/response cycle.

        Args:
            state: Defines the interaction with the backend plugin.

        """
        await self._read_proxy_protocol()
        self._print('%s +++| %s', str(socket_info.get()))
        bad_commands = 0
        try:
            greeting = await self._exec(state.do_greeting())
        except ResponseError as exc:
            resp = exc.get_response(b'*')
            resp.condition = ResponseBye.condition
            await self.write_response(resp)
            return
        else:
            await self.write_response(greeting)
        while True:
            try:
                cmd = await self.read_command(state)
            except (ConnectionError, EOFError):
                break
            except CancelledError:
                await self.send_error_disconnect()
                break
            except Exception:
                await self.send_error_disconnect()
                raise
            else:
                prev_cmd = current_command.set(cmd)
                try:
                    if isinstance(cmd, AuthenticateCommand):
                        creds = await self.authenticate(state, cmd.mech_name)
                        response = await self._exec(
                            state.do_authenticate(cmd, creds))
                    elif isinstance(cmd, IdleCommand):
                        response = await self.idle(state, cmd)
                    else:
                        response = await self._exec(state.do_command(cmd))
                except ResponseError as exc:
                    resp = exc.get_response(cmd.tag)
                    await self.write_response(resp)
                    if resp.is_terminal:
                        break
                except AuthenticationError as exc:
                    msg = bytes(str(exc), 'utf-8', 'surrogateescape')
                    resp = ResponseBad(cmd.tag, msg)
                    await self.write_response(resp)
                except TimeoutError:
                    resp = ResponseNo(cmd.tag, b'Operation timed out.',
                                      ResponseCode.of(b'TIMEOUT'))
                    await self.write_response(resp)
                except CancelledError:
                    await self.send_error_disconnect()
                    break
                except Exception:
                    await self.send_error_disconnect()
                    raise
                else:
                    await self.write_response(response)
                    if response.is_bad:
                        bad_commands += 1
                        if self.bad_command_limit \
                                and bad_commands >= self.bad_command_limit:
                            msg = b'Too many errors, disconnecting.'
                            response.add_untagged(ResponseBye(msg))
                    else:
                        bad_commands = 0
                    if response.is_terminal:
                        break
                    if isinstance(cmd, StartTLSCommand) \
                            and isinstance(response, ResponseOk):
                        await self.start_tls()
                finally:
                    await state.do_cleanup()
                    current_command.reset(prev_cmd)
        self._print('%s ---| %s', b'<disconnected>')
