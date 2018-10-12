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

from typing import Dict, Type, Tuple, Any

from .. import Parseable, NotParseable, Space, EndLine, Params
from ..primitives import Atom
from ..specials import Tag

__all__ = ['CommandNotFound', 'BadCommand', 'Command', 'CommandNoArgs',
           'CommandAny', 'CommandAuth', 'CommandNonAuth', 'CommandSelect',
           'Commands']


class Command(Parseable[Any]):
    """Base class to represent the commands available to clients.

    :param tag: The tag parsed from the beginning of the command line.

    """

    #: The command key, e.g. ``b'NOOP'``.
    command: bytes = b''

    def __init__(self, tag: bytes) -> None:
        super().__init__()

        #: The tag parsed from the beginning of the command line.
        self.tag = tag

    @classmethod
    def parse(cls, buf: bytes, params: Params) -> Tuple['Command', bytes]:
        raise RuntimeError

    @property
    def with_uid(self) -> bool:
        return False

    def __bytes__(self):
        return b' '.join((self.tag, self.command))


class CommandNoArgs(Command):
    """Convenience class used to fail parsing when args are given to a command
    that expects nothing.

    """

    @classmethod
    def parse(cls, buf: bytes, params: Params) \
            -> Tuple['CommandNoArgs', bytes]:
        _, buf = EndLine.parse(buf, params)
        return cls(params.tag), buf


class CommandAny(Command):
    """Represents a command available at any stage of the IMAP session.

    """
    pass


class CommandAuth(Command):
    """Represents a command available when the IMAP session has been
    authenticated.

    """
    pass


class CommandNonAuth(Command):
    """Represents a command available only when the IMAP session has not yet
    authenticated.

    """
    pass


class CommandSelect(CommandAuth):
    """Represents a command available only when the IMAP session has been
    authenticated and a mailbox has been selected.

    """
    pass


class Commands:
    """Contains the set of all known IMAP commands and the ability to parse."""

    def __init__(self):
        super().__init__()
        self.commands: Dict[bytes, Type[Command]] = {}
        self._load_commands()

    def _load_commands(self):
        from . import any, auth, nonauth, select  # NOQA
        for mod in (any, auth, nonauth, select):
            for command_name in mod.__all__:
                command = getattr(mod, command_name)
                self.commands[command.command] = command

    def parse(self, buf: bytes, params: Params) -> Tuple[Command, bytes]:
        tag = Tag(b'*')
        try:
            tag, buf = Tag.parse(buf, params)
            _, buf = Space.parse(buf, params)
            atom, buf = Atom.parse(buf, params)
            command = atom.value.upper()
        except NotParseable:
            raise CommandNotFound(buf, tag.value)
        cmd_type = self.commands.get(command)
        params = params.copy(tag=tag.value)
        if cmd_type:
            try:
                return cmd_type.parse(buf, params)
            except NotParseable as exc:
                raise BadCommand(exc.buf, tag.value, cmd_type)
        raise CommandNotFound(buf, tag.value, command)

    def __bytes__(self):
        raise NotImplementedError


class BadCommand(NotParseable):
    """Error indicating the data was not parseable because the command had
    invalid arguments.

    """

    def __init__(self, buf: bytes, tag: bytes, command: Type[Command]) -> None:
        super().__init__(buf)
        self.tag = tag
        self.command = command
        self._raw = None

    def __bytes__(self):
        if self._raw is None:
            self._raw = b': '.join((self.command.command, super().__bytes__()))
        return self._raw


class CommandNotFound(NotParseable):
    """Error indicating the data was not parseable because the command was not
    found.

    """

    def __init__(self, buf: bytes, tag: bytes, command: bytes = None) -> None:
        super().__init__(buf)
        self.tag = tag
        self.command = command

    def __bytes__(self):
        if self.command:
            return b'Command Not Found: %b' % self.command
        else:
            return b'Command Not Given'
