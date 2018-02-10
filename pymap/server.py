# Copyright (c) 2018 Ian C. Good
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
import binascii
import re
from base64 import b64encode, b64decode

from pysasl import (ServerChallenge, AuthenticationError,
                    AuthenticationCredentials)

from .exceptions import ResponseError, CloseConnection
from .parsing import RequiresContinuation
from .parsing.command import BadCommand, Commands
from .parsing.command.nonauth import AuthenticateCommand, LoginCommand
from .parsing.response import (ResponseContinuation, ResponseBadCommand,
                               ResponseBad, ResponseBye)
from .state import ConnectionState

__all__ = ['Disconnected', 'IMAPServer']


class Disconnected(Exception):
    pass


class IMAPServer(object):

    def __init__(self, debug, reader, writer):
        super().__init__()
        self.commands = Commands()
        self.reader = reader
        self.writer = writer
        if not debug:
            self._print = self._noop_print

    @classmethod
    async def callback(cls, login, debug, reader, writer):
        state = ConnectionState(login)
        await cls(debug, reader, writer).run(state)

    def _print(self, prefix: str, output: bytes):
        prefix = prefix % self.writer.get_extra_info('socket').fileno()
        lines = re.split(br'\r?\n', output)
        if not lines[-1]:
            lines = lines[:-1]
        for line in lines:
            line_str = str(line, 'utf-8', 'replace')
            print(prefix, line_str)

    @classmethod
    def _noop_print(cls, prefix: str, output: bytes):
        pass

    async def read_continuation(self, literal_length):
        try:
            extra_literal = await self.reader.readexactly(literal_length)
        except asyncio.IncompleteReadError:
            raise Disconnected
        extra_line = await self.reader.readline()
        if self.reader.at_eof():
            raise Disconnected
        extra = extra_literal + extra_line
        self._print('%d -->|', extra)
        return extra

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
        self._print('%d -->|', line)
        conts = []
        while True:
            try:
                cmd, _ = self.commands.parse(line, continuations=conts.copy())
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
        self._print('%d <--|', raw)

    async def send_error_disconnect(self):
        resp = ResponseBye(b'Unhandled server error.')
        try:
            await self.write_response(resp)
            self.writer.close()
        except IOError:
            pass

    async def run(self, state):
        self._print('%d +++|', b'<connected>')
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
                except ResponseError as exc:
                    resp = exc.get_response(cmd.tag)
                    await self.write_response(resp)
                    if isinstance(exc, CloseConnection):
                        break
                except AuthenticationError as exc:
                    resp = ResponseBad(cmd.tag, bytes(str(exc), 'utf-8'))
                    await self.write_response(resp)
                except Exception:
                    await self.send_error_disconnect()
                    raise
                else:
                    await self.write_response(response)
        self._print('%d ---|', b'<disconnected>')
        self.writer.close()
