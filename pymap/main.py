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

import asyncio

from pysasl import IssueChallenge, AuthenticationError, AuthenticationResult

from .state import CloseConnection, ConnectionState
from pymap.parsing.command import BadCommand, Command
from pymap.parsing.response import ResponseContinuation, ResponseBadCommand
from pymap.parsing.command.nonauth import AuthenticateCommand, LoginCommand
from pymap.parsing import RequiresContinuation


class Disconnected(Exception):
    pass


class IMAPServer(object):

    def __init__(self, reader, writer):
        super().__init__()
        self.reader = reader
        self.writer = writer

    @classmethod
    @asyncio.coroutine
    def callback(cls, reader, writer):
        yield from cls(reader, writer).run()

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
                cont = ResponseContinuation(exc.challenge.challenge)
                yield from cont.send_stream(self.writer)
                exc.challenge.response = yield from self.read_continuation(0)
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
                cmd, _ = Command.parse(line, continuations = conts.copy())
            except RequiresContinuation as req:
                cont = ResponseContinuation(req.message)
                yield from cont.send_stream(self.writer)
                ret = yield from self.read_continuation(req.literal_length)
                conts.append(ret)
            else:
                return cmd

    @asyncio.coroutine
    def run(self):
        state = ConnectionState(self.writer.transport)
        greeting = yield from state.do_greeting()
        yield from greeting.send_stream(self.writer)
        while True:
            try:
                cmd = yield from self.read_command()
            except BadCommand as bad:
                yield from ResponseBadCommand(bad).send_stream(self.writer)
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
                except CloseConnection as close:
                    yield from close.response.send_stream(self.writer)
                    break
                else:
                    yield from response.send_stream(self.writer)
        self.writer.close()


def main():
    loop = asyncio.get_event_loop()
    coro = asyncio.start_server(IMAPServer.callback, port=1143, loop=loop)
    server = loop.run_until_complete(coro)

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        print()

    server.close()
    loop.run_until_complete(server.wait_closed())
    loop.close()
