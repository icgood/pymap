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

import re

from .. import Parseable, NotParseable, EndLine
from ..primitives import Atom, String
from . import CommandNonAuth, CommandNoArgs, BadCommand

__all__ = ['StartTLSCommand']


class StartTLSCommand(CommandNonAuth, CommandNoArgs):
    command = b'STARTTLS'

CommandNonAuth._commands.append(StartTLSCommand)


class LoginCommand(CommandNonAuth):
    command = b'LOGIN'

    def __init__(self, userid, password):
        super(LoginCommand, self).__init__()
        self.userid = userid
        self.password = password

    @classmethod
    def _parse(cls, buf, continuation=None, **kwargs):
        userid, buf = Parseable.parse(buf, expected=[Atom, String],
                                      continuation=continuation)
        buf = cls._enforce_whitespace(buf)
        password, buf = Parseable.parse(buf, expected=[Atom, String],
                                        continuation=continuation)
        _, buf = EndLine.parse(buf)
        return cls(userid.value, password.value), buf

CommandNonAuth._commands.append(LoginCommand)
