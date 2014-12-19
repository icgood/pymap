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
from socket import getfqdn

from pymap.core import PymapError
from pymap.parsing.command import (CommandAny, CommandAuth, CommandNonAuth,
    CommandSelect)
from pymap.parsing.response import (ResponseContinuation, ResponseOk,
    ResponseBad, ResponseNo, ResponseBye)
from pymap.parsing.response.code import Capability

__all__ = ['CloseConnection', 'ConnectionState']

fqdn = getfqdn().encode('ascii')


class CloseConnection(PymapError):
    """Raised when the connection should be closed immediately after sending
    the provided response.

    :param response: The response to send before closing the connection.
    :type response: :class:`~pymap.parsing.response.Response`

    """

    def __init__(self, response):
        super(CloseConnection, self).__init__()
        self.response = response


class ConnectionState(object):

    def __init__(self, transport):
        super(ConnectionState, self).__init__()
        self.transport = transport
        self.authed = None
        self.selected = None

    @asyncio.coroutine
    def do_greeting(self):
        code = Capability()
        return ResponseOk(b'*', b'Server ready ' + fqdn, code)

    @asyncio.coroutine
    def do_command(self, cmd):
        if self.authed and isinstance(cmd, CommandNonAuth):
            msg = cmd.command + b': Already authenticated.'
            return ResponseBad(cmd.tag, msg)
        elif not self.authed and isinstance(cmd, CommandAuth):
            msg = cmd.command + b': Must authenticate first.'
            return ResponseBad(cmd.tag, msg)
        elif not self.selected and isinstance(cmd, CommandSelect):
            msg = cmd.command + b': Must select a mailbox first.'
            return ResponseBad(cmd.tag, msg)
        if cmd.command in (b'LOGIN', ):
            self.authed = cmd.userid
            return ResponseOk(cmd.tag, b'Authentication successful.')
        elif cmd.command == b'SELECT':
            self.selected = cmd.mailbox
            return ResponseOk(cmd.tag, b'Selected mailbox.')
        elif cmd.command == b'LOGOUT':
            response = ResponseOk(cmd.tag, b'Logout successful.')
            response.add_data(ResponseBye(b'Logging out.'))
            raise CloseConnection(response)
        return ResponseNo(cmd.tag, cmd.command + b' Not Implemented')
