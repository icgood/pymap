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
import asyncio

from pkg_resources import iter_entry_points

from pysasl import IssueChallenge, AuthenticationError, AuthenticationResult

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
    @asyncio.coroutine
    def callback(cls, backend, reader, writer):
        yield from cls(backend, reader, writer).run()

    @asyncio.coroutine
    def read_continuation(self, literal_length):
        try:
            extra_literal = yield from self.reader.readexactly(literal_length)
        except asyncio.IncompleteReadError:
            raise Disconnected
        extra_line = yield from self.reader.readline()
        if self.reader.at_eof():
            raise Disconnected
        return extra_literal + extra_line

    @asyncio.coroutine
    def authenticate(self, state, mech):
        responses = []
        while True:
            try:
                result = mech.server_attempt(responses)
            except IssueChallenge as exc:
                chal_bytes = b64encode(exc.challenge.challenge.encode('utf-8'))
                cont = ResponseContinuation(chal_bytes)
                yield from self.write_response(cont)
                resp_bytes = yield from self.read_continuation(0)
                exc.challenge.response = b64decode(resp_bytes).decode('utf-8')
                responses.append(exc.challenge)
            else:
                break
        return result

    @asyncio.coroutine
    def read_command(self):
        line = yield from self.reader.readline()
        if self.reader.at_eof():
            raise Disconnected
        conts = []
        while True:
            try:
                cmd, _ = Command.parse(line, continuations=conts.copy())
            except RequiresContinuation as req:
                cont = ResponseContinuation(req.message)
                yield from self.write_response(cont)
                ret = yield from self.read_continuation(req.literal_length)
                conts.append(ret)
            else:
                return cmd

    @asyncio.coroutine
    def write_response(self, resp):
        raw = bytes(resp)
        self.writer.write(raw)
        yield from self.writer.drain()

    @asyncio.coroutine
    def run(self):
        state = ConnectionState(self.writer.transport, self.backend)
        greeting = yield from state.do_greeting()
        yield from self.write_response(greeting)
        while True:
            try:
                cmd = yield from self.read_command()
            except BadCommand as bad:
                yield from self.write_response(ResponseBadCommand(bad))
            except Disconnected:
                break
            else:
                try:
                    if isinstance(cmd, AuthenticateCommand):
                        auth = yield from self.authenticate(state, cmd.mech)
                        response = yield from state.do_authenticate(cmd, auth)
                    elif isinstance(cmd, LoginCommand):
                        auth = AuthenticationResult(cmd.userid, cmd.password)
                        response = yield from state.do_authenticate(cmd, auth)
                    else:
                        response = yield from state.do_command(cmd)
                except AuthenticationError as exc:
                    resp = ResponseBad(cmd.tag, bytes(str(exc), 'utf-8'))
                    yield from self.write_response(resp)
                except CloseConnection as close:
                    yield from self.write_response(close.response)
                    break
                except Exception:
                    resp = ResponseBye(b'Unhandled server error.')
                    try:
                        yield from self.write_response(resp)
                        self.writer.close()
                    except Exception:
                        pass
                    raise
                else:
                    yield from self.write_response(response)
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
