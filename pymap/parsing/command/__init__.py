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

from .. import Parseable, NotParseable, Space, EndLine
from ..primitives import Atom

__all__ = ['CommandNotFound', 'BadCommand', 'Tag', 'Command', 'CommandNoArgs',
           'CommandAny', 'CommandAuth', 'CommandNonAuth', 'CommandSelect']


class CommandNotFound(NotParseable):
    """Error indicating the data was not parseable because the command was not
    found.

    """

    def __init__(self, buf, command):
        super(CommandNotFound, self).__init__(buf)
        self.command = command


class BadCommand(NotParseable):
    """Error indicating the data was not parseable because the command had
    invalid arguments.

    """

    def __init__(self, command, *args):
        super(BadCommand, self).__init__(*args)
        self.command = command


class Tag(Parseable):
    """Represents the tag prefixed to every client command in an IMAP stream.

    :param bytes tag: The contents of the tag.

    """

    _pattern = re.compile(br'[\x21\x23\x24\x26\x27\x2C-\x5B'
                          br'\x5D\x5E-\x7A\x7C\x7E]+')

    #: May be passed in to the constructor to indicate the continuation
    #: response tag, ``+``.
    CONTINUATION = object()

    def __init__(self, tag=None):
        super(Tag, self).__init__()
        if not tag:
            self.value = b'*'
        elif tag == self.CONTINUATION:
            self.value = b'+'
        else:
            self.value = tag

    @classmethod
    def parse(cls, buf, **kwargs):
        start = cls._whitespace_length(buf)
        match = cls._pattern.match(buf, start)
        if not match:
            raise NotParseable(buf)
        return cls(match.group(0)), buf[match.end(0):]

    def __bytes__(self):
        return self.value

Parseable.register_type(Tag)


class Command(Parseable):
    """Base class to represent the commands available to clients.

    :param bytes tag: The tag parsed from the beginning of the command line.

    """

    def __init__(self, tag):
        super(Command, self).__init__()
        self.tag = tag

    @classmethod
    def parse(cls, buf, **kwargs):
        from . import any, auth, nonauth, select
        tag, buf = Tag.parse(buf)
        _, buf = Space.parse(buf)
        atom, buf = Atom.parse(buf)
        command = atom.value.upper()
        for cmd_type in [CommandAny, CommandAuth,
                         CommandNonAuth, CommandSelect]:
            for cmd_subtype in cmd_type._commands:
                regex = getattr(cmd_subtype, 'regex', None) or \
                    re.compile(b'^'+cmd_subtype.command+b'$')
                match = regex.match(command)
                if match:
                    try:
                        return cmd_subtype._parse(tag.value, buf, **kwargs)
                    except NotParseable as exc:
                        raise BadCommand(cmd_subtype, *exc.args)
        raise CommandNotFound(buf, command)

Parseable.register_type(Command)


class CommandNoArgs(Command):
    """Convenience class used to fail parsing when args are given to a command
    that expects nothing.

    """

    @classmethod
    def _parse(cls, tag, buf, **kwargs):
        _, buf = EndLine.parse(buf)
        return cls(tag), buf


class CommandAny(Command):
    """Represents a command available at any stage of the IMAP session.

    """

    _commands = []


class CommandAuth(Command):
    """Represents a command available when the IMAP session has been
    authenticated.

    """

    _commands = []


class CommandNonAuth(Command):
    """Represents a command available only when the IMAP session has not yet
    authenticated.

    """

    _commands = []


class CommandSelect(CommandAuth):
    """Represents a command available only when the IMAP session has been
    authenticated and a mailbox has been selected.

    """

    _commands = []
