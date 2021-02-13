
from __future__ import annotations

from collections.abc import Collection
from typing import Optional

from . import Space, Params
from .command import Command
from .command.any import CapabilityCommand, LogoutCommand, NoOpCommand
from .command.auth import AppendCommand, CreateCommand, DeleteCommand, \
    ExamineCommand, ListCommand, LSubCommand, RenameCommand, SelectCommand, \
    StatusCommand, SubscribeCommand, UnsubscribeCommand
from .command.nonauth import AuthenticateCommand, LoginCommand, StartTLSCommand
from .command.select import CheckCommand, CloseCommand, ExpungeCommand, \
    CopyCommand, MoveCommand, FetchCommand, StoreCommand, SearchCommand, \
    UidCommand, UidCopyCommand, UidMoveCommand, UidExpungeCommand, \
    UidFetchCommand, UidSearchCommand, UidStoreCommand, IdleCommand
from .exceptions import NotParseable
from .primitives import Atom
from .specials import Tag

__all__ = ['builtin_commands', 'InvalidCommand', 'Commands']

#: List of built-in commands. These commands are automatically registered by a
#: new :class:`Commands` object.
builtin_commands: Collection[type[Command]] = [
    CapabilityCommand, LogoutCommand, NoOpCommand, AppendCommand,
    CreateCommand, DeleteCommand, ExamineCommand, ListCommand, LSubCommand,
    RenameCommand, SelectCommand, StatusCommand, SubscribeCommand,
    UnsubscribeCommand, AuthenticateCommand, LoginCommand, StartTLSCommand,
    CheckCommand, CloseCommand, ExpungeCommand, CopyCommand, MoveCommand,
    FetchCommand, StoreCommand, SearchCommand, UidCommand, UidCopyCommand,
    UidMoveCommand, UidExpungeCommand, UidFetchCommand, UidSearchCommand,
    UidStoreCommand, IdleCommand]


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
                 command_type: Optional[type[Command]] = None) -> None:
        super().__init__(params.tag)
        self._parse_exc = parse_exc
        self._command = command
        self._command_type = command_type

    @property
    def value(self) -> bytes:
        return self._command or b''

    @property
    def message(self) -> bytes:
        """The message to include in a BAD response."""
        if not self.command_name:
            return b'Command not given.'
        elif not self.command_type:
            return b'%b: Command not implemented.' % (self.command_name, )
        else:
            return b'%b: Invalid arguments.' % (self.command_name, )

    @property
    def command_name(self) -> Optional[bytes]:
        """The command name, if the name could be parsed."""
        return self._command

    @property
    def command_type(self) -> Optional[type[Command]]:
        """The command type, if parsing failed due to invalid arguments."""
        return self._command_type

    @property
    def parse_exc(self) -> Optional[NotParseable]:
        """The parsing exception, if any."""
        return self._parse_exc

    @classmethod
    def parse(cls, buf: memoryview, params: Params) \
            -> tuple[InvalidCommand, memoryview]:
        raise RuntimeError('Do not call')


class Commands:
    """Manages the set of all known IMAP commands and the ability to parse."""

    __slots__ = ['commands']

    def __init__(self) -> None:
        super().__init__()
        self.commands: dict[bytes, type[Command]] = {}
        self._load_commands()

    def _load_commands(self):
        for cmd in builtin_commands:
            self.register(cmd)

    def register(self, cmd: type[Command]) -> None:
        """Register a new IMAP command.

        Args:
            cmd: The new command type.

        """
        self.commands[cmd.command] = cmd

    def deregister(self, name: bytes) -> None:
        """Deregister an IMAP command by name. Does nothing if the command is
        not registered.

        Args:
            name: The IMAP command name.

        """
        self.commands.pop(name.upper(), None)

    def parse(self, buf: memoryview, params: Params) \
            -> tuple[Command, memoryview]:
        """Parse the given bytes into a command. The basic syntax is a tag
        string, a command name, possibly some arguments, and then an endline.
        If the command has a complete structure but cannot be parsed, an
        :class:`InvalidCommand` is returned.

        Args:
            buf: The bytes to parse.
            params: The parsing parameters.

        """
        try:
            tag, buf = Tag.parse(buf, params)
        except NotParseable as exc:
            return InvalidCommand(params, exc), buf[0:0]
        else:
            params = params.copy(tag=tag.value)
        cmd_parts: list[bytes] = []
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
