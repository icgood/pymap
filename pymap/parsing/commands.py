from typing import Dict, Type, Tuple

from . import Space, Params
from .command import Command,  any, auth, nonauth, select
from .exceptions import NotParseable, CommandNotFound, CommandInvalid
from .primitives import Atom
from .specials import Tag

__all__ = ['Commands']


class Commands:
    """Contains the set of all known IMAP commands and the ability to parse."""

    def __init__(self) -> None:
        super().__init__()
        self.commands: Dict[bytes, Type[Command]] = {}
        self._load_commands()

    def _load_commands(self):
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
            raise CommandNotFound(tag.value)
        cmd_type = self.commands.get(command)
        if not cmd_type:
            raise CommandNotFound(tag.value, command)
        params = params.copy(tag=tag.value, command_name=command)
        try:
            return cmd_type.parse(buf, params)
        except NotParseable as exc:
            raise CommandInvalid(tag.value, command) from exc

    def __bytes__(self) -> bytes:
        raise NotImplementedError
