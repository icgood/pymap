
from typing import Optional, Type, Tuple, Dict, List

from . import Space, Params
from .command import Command, any, auth, nonauth, select
from .exceptions import NotParseable
from .primitives import Atom
from .specials import Tag

__all__ = ['InvalidCommand', 'Commands']


class InvalidCommand(Command):
    """An invalid command, either because the tag or command name could not be
    parsed, the command name was not recognized, or a known command was given
    invalid arguments.

    Args:
        params: The parsing parameters
        parse_exc: The exception that caused the failure, if any.
        command: The command name, if available.
        command_type: The command type, if available.

    """

    command = b'[INVALID]'

    def __init__(self, params: Params, parse_exc: Optional[NotParseable],
                 command: Optional[bytes] = None,
                 command_type: Optional[Type[Command]] = None) -> None:
        super().__init__(params.tag)
        self._parse_exc = parse_exc
        self._command = command
        self._command_type = command_type

    @property
    def value(self) -> bytes:
        return self._command or b''

    @property
    def command_name(self) -> Optional[bytes]:
        """The command name, if the name could be parsed."""
        return self._command

    @property
    def command_type(self) -> Optional[Type[Command]]:
        """The command type, if parsing failed due to invalid arguments."""
        return self._command_type

    @property
    def parse_exc(self) -> Optional[NotParseable]:
        """The parsing exception, if any."""
        return self._parse_exc

    @classmethod
    def parse(cls, buf: memoryview, params: Params) \
            -> Tuple['InvalidCommand', memoryview]:
        raise RuntimeError('Do not call')


class Commands:
    """Contains the set of all known IMAP commands and the ability to parse."""

    __slots__ = ['commands']

    def __init__(self) -> None:
        super().__init__()
        self.commands: Dict[bytes, Type[Command]] = {}
        self._load_commands()

    def _load_commands(self):
        for mod in (any, auth, nonauth, select):
            for command_name in mod.__all__:
                command = getattr(mod, command_name)
                self.commands[command.command] = command

    def parse(self, buf: memoryview, params: Params) \
            -> Tuple[Command, memoryview]:
        """Parse the given bytes into a command. The basic syntax is a tag
        string, a command name, possibly some arguments, and then an endline.
        If the command has a complete structure but cannot be parsed, an
        :class:`InvalidCommand` is returned.

        Args:
            buf: The bytes to parse.
            params: The parsing parameters.

        """
        tag = Tag(params.tag)
        try:
            tag, buf = Tag.parse(buf, params)
        except NotParseable as exc:
            return InvalidCommand(params, exc), buf[0:0]
        else:
            params = params.copy(tag=tag.value)
        cmd_parts: List[bytes] = []
        while True:
            try:
                _, buf = Space.parse(buf, params)
                atom, buf = Atom.parse(buf, params)
                cmd_parts.append(atom.value.upper())
            except NotParseable as exc:
                return InvalidCommand(params, exc), buf[0:0]
            command = b' '.join(cmd_parts)
            cmd_type = self.commands.get(command)
            if not cmd_type:
                return InvalidCommand(params, None, command), buf[0:0]
            elif not cmd_type.compound:
                break
        params = params.copy(command_name=command)
        try:
            return cmd_type.parse(buf, params)
        except NotParseable as exc:
            return InvalidCommand(params, exc, command, cmd_type), buf[0:0]
