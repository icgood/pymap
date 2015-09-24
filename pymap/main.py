# Copyright (c) 2014 Ian C. Good
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#

"""IMAP server with pluggable Python backends."""

from functools import partial
from base64 import b64encode, b64decode
from argparse import ArgumentParser
import binascii
import asyncio

from pkg_resources import iter_entry_points

from pysasl import (ServerChallenge, AuthenticationError,
                    AuthenticationCredentials)

from .core import __version__
from .state import CloseConnection, ConnectionState
from .parsing.command import BadCommand, Command
from .parsing.response import (ResponseContinuation, ResponseBadCommand,
                               ResponseBad, ResponseBye)
from .parsing.command.nonauth import AuthenticateCommand, LoginCommand
from .parsing import RequiresContinuation


class Disconnected(Exception):
    pass


class IMAPServer(object):

    def __init__(self, backend, reader, writer):
        super().__init__()
        self.backend = backend
        self.reader = reader
        self.writer = writer

    @classmethod
    async def callback(cls, backend, reader, writer):
        await cls(backend, reader, writer).run()

    async def read_continuation(self, literal_length):
        try:
            extra_literal = await self.reader.readexactly(literal_length)
        except asyncio.IncompleteReadError:
            raise Disconnected
        extra_line = await self.reader.readline()
        if self.reader.at_eof():
            raise Disconnected
        return extra_literal + extra_line

    async def authenticate(self, state, mech_name):
        mech = state.auth.get(mech_name)
        if not mech:
            return
        responses = []
        while True:
            try:
                return mech.server_attempt(responses)
            except ServerChallenge as exc:
                chal_bytes = b64encode(exc.get_challenge())
                cont = ResponseContinuation(chal_bytes)
                await self.write_response(cont)
                resp_bytes = await self.read_continuation(0)
                try:
                    exc.set_response(b64decode(resp_bytes))
                except binascii.Error as exc:
                    raise AuthenticationError(exc)
                if resp_bytes.rstrip(b'\r\n') == b'*':
                    raise AuthenticationError('Authentication canceled.')
                responses.append(exc)

    async def read_command(self):
        line = await self.reader.readline()
        if self.reader.at_eof():
            raise Disconnected
        conts = []
        while True:
            try:
                cmd, _ = Command.parse(line, continuations=conts.copy())
            except RequiresContinuation as req:
                cont = ResponseContinuation(req.message)
                await self.write_response(cont)
                ret = await self.read_continuation(req.literal_length)
                conts.append(ret)
            else:
                return cmd

    async def write_response(self, resp):
        raw = bytes(resp)
        self.writer.write(raw)
        await self.writer.drain()

    async def send_error_disconnect(self):
        resp = ResponseBye(b'Unhandled server error.')
        try:
            await self.write_response(resp)
            self.writer.close()
        except Exception:
            pass

    async def run(self):
        state = ConnectionState(self.writer.transport, self.backend)
        greeting = await state.do_greeting()
        await self.write_response(greeting)
        while True:
            try:
                cmd = await self.read_command()
            except BadCommand as bad:
                await self.write_response(ResponseBadCommand(bad))
            except (ConnectionResetError, BrokenPipeError):
                break
            except Disconnected:
                break
            except Exception:
                await self.send_error_disconnect()
                raise
            else:
                try:
                    if isinstance(cmd, AuthenticateCommand):
                        auth = await self.authenticate(state, cmd.mech_name)
                        response = await state.do_authenticate(cmd, auth)
                    elif isinstance(cmd, LoginCommand):
                        auth = AuthenticationCredentials(
                            cmd.userid.decode('utf-8'),
                            cmd.password.decode('utf-8'))
                        response = await state.do_authenticate(cmd, auth)
                    else:
                        response = await state.do_command(cmd)
                except AuthenticationError as exc:
                    resp = ResponseBad(cmd.tag, bytes(str(exc), 'utf-8'))
                    await self.write_response(resp)
                except CloseConnection as close:
                    await self.write_response(close.response)
                    break
                except Exception:
                    await self.send_error_disconnect()
                    raise
                else:
                    await self.write_response(response)
        self.writer.close()


def _load_backends():
    return {entry_point.name: entry_point.load()
            for entry_point in iter_entry_points('pymap.backend')}


def main():
    backends = _load_backends()

    parser = ArgumentParser(description=__doc__)
    parser.add_argument('--version', action='version',
                        version='%(prog)s'+__version__)
    subparsers = parser.add_subparsers(dest='backend',
                                       help='Which pymap backend to use.')
    for mod in backends.values():
        mod.add_subparser(subparsers)
    args = parser.parse_args()

    try:
        backend = backends[args.backend]
    except KeyError:
        parser.error('Expected backend name.')

    callback = partial(IMAPServer.callback, backend.init(args))
    loop = asyncio.get_event_loop()
    coro = asyncio.start_server(callback, port=1143, loop=loop)
    server = loop.run_until_complete(coro)

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        print()

    server.close()
    loop.run_until_complete(server.wait_closed())
    loop.close()
