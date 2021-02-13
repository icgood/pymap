
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import ClassVar, Final, Optional

from pymap.parsing import Parseable, Params, EndLine
from pymap.parsing.exceptions import NotParseable
from pymap.parsing.primitives import Atom, Number, String, QuotedString

__all__ = ['Command', 'NoOpCommand', 'CapabilityCommand', 'StartTLSCommand',
           'AuthenticateCommand', 'UnauthenticateCommand', 'LogoutCommand',
           'HaveSpaceCommand', 'PutScriptCommand', 'ListScriptsCommand',
           'SetActiveCommand', 'GetScriptCommand', 'DeleteScriptCommand',
           'RenameScriptCommand', 'CheckScriptCommand']


class Command(Parseable[bytes]):
    """Base class for ManageSieve commands."""

    #: The command key, e.g. ``b'NOOP'``.
    command: ClassVar[bytes] = b''

    _commands: Optional[Mapping[bytes, type[Command]]] = None

    @property
    def value(self) -> bytes:
        """The command name."""
        return self.command

    def __bytes__(self) -> bytes:
        return self.command

    def __repr__(self) -> str:
        return '<%s>' % (type(self).__name__)

    @classmethod
    def _all_commands(cls) -> Sequence[type[Command]]:
        return [
            NoOpCommand, CapabilityCommand, StartTLSCommand,
            AuthenticateCommand, UnauthenticateCommand, LogoutCommand,
            HaveSpaceCommand, PutScriptCommand, ListScriptsCommand,
            SetActiveCommand, GetScriptCommand, DeleteScriptCommand,
            RenameScriptCommand, CheckScriptCommand]

    @classmethod
    def _get_commands(cls) -> Mapping[bytes, type[Command]]:
        if cls._commands is None:
            mapping = {}
            for cmd in cls._all_commands():
                mapping[cmd.command] = cmd
            cls._commands = mapping
        return cls._commands

    @classmethod
    def _parse_script_name(self, buf: memoryview, params: Params,
                           allow_empty: bool = False) \
            -> tuple[str, memoryview]:
        name_obj, after = String.parse(buf, params)
        if not allow_empty and not name_obj.value:
            raise NotParseable(buf)
        try:
            return name_obj.value.decode('utf-8'), after
        except UnicodeError as exc:
            raise NotParseable(buf) from exc

    @classmethod
    def parse(cls, buf: memoryview, params: Params) \
            -> tuple[Command, memoryview]:
        commands = cls._get_commands()
        cmd_name, after = Atom.parse(buf, params)
        try:
            cmd_type = commands[cmd_name.value.upper()]
        except KeyError:
            raise NotParseable(buf)
        else:
            buf = after
        cmd, buf = cmd_type.parse(buf, params)
        return cmd, buf


class NoOpCommand(Command):

    command = b'NOOP'

    def __init__(self, tag: Optional[bytes]) -> None:
        super().__init__()
        self.tag: Final = tag

    @classmethod
    def parse(cls, buf: memoryview, params: Params) \
            -> tuple[NoOpCommand, memoryview]:
        whitespace = cls._whitespace_length(buf)
        tag: Optional[bytes] = None
        if whitespace > 0:
            buf = buf[whitespace:]
            try:
                tag_obj, buf = String.parse(buf, params)
            except NotParseable:
                pass
            else:
                tag = tag_obj.value
        _, buf = EndLine.parse(buf, params)
        return cls(tag), buf


class CapabilityCommand(Command):

    command = b'CAPABILITY'

    @classmethod
    def parse(cls, buf: memoryview, params: Params) \
            -> tuple[CapabilityCommand, memoryview]:
        _, buf = EndLine.parse(buf, params)
        return cls(), buf


class StartTLSCommand(Command):

    command = b'STARTTLS'

    @classmethod
    def parse(cls, buf: memoryview, params: Params) \
            -> tuple[StartTLSCommand, memoryview]:
        _, buf = EndLine.parse(buf, params)
        return cls(), buf


class AuthenticateCommand(Command):

    command = b'AUTHENTICATE'

    def __init__(self, mech_name: bytes, initial_data: bytes = None) -> None:
        super().__init__()
        self.mech_name: Final = mech_name
        self.initial_data: Final = initial_data

    @classmethod
    def parse(cls, buf: memoryview, params: Params) \
            -> tuple[AuthenticateCommand, memoryview]:
        mech_name, buf = QuotedString.parse(buf, params)
        try:
            data_obj, buf = String.parse(buf, params)
        except NotParseable:
            initial_data: Optional[bytes] = None
        else:
            initial_data = data_obj.value
        return cls(mech_name.value, initial_data), buf


class UnauthenticateCommand(Command):

    command = b'UNAUTHENTICATE'

    @classmethod
    def parse(cls, buf: memoryview, params: Params) \
            -> tuple[UnauthenticateCommand, memoryview]:
        _, buf = EndLine.parse(buf, params)
        return cls(), buf


class LogoutCommand(Command):

    command = b'LOGOUT'

    @classmethod
    def parse(cls, buf: memoryview, params: Params) \
            -> tuple[LogoutCommand, memoryview]:
        _, buf = EndLine.parse(buf, params)
        return cls(), buf


class HaveSpaceCommand(Command):

    command = b'HAVESPACE'

    def __init__(self, script_name: str, size: int) -> None:
        super().__init__()
        self.script_name: Final = script_name
        self.size: Final = size

    @classmethod
    def parse(cls, buf: memoryview, params: Params) \
            -> tuple[HaveSpaceCommand, memoryview]:
        script_name, after = cls._parse_script_name(buf, params)
        if not script_name:
            raise NotParseable(buf)
        size, buf = Number.parse(after, params)
        _, buf = EndLine.parse(buf, params)
        return cls(script_name, size.value), buf


class PutScriptCommand(Command):

    command = b'PUTSCRIPT'

    def __init__(self, script_name: str, script_data: bytes) -> None:
        super().__init__()
        self.script_name: Final = script_name
        self.script_data: Final = script_data

    @classmethod
    def parse(cls, buf: memoryview, params: Params) \
            -> tuple[PutScriptCommand, memoryview]:
        script_name, buf = cls._parse_script_name(buf, params)
        script_data, buf = String.parse(buf, params)
        _, buf = EndLine.parse(buf, params)
        return cls(script_name, script_data.value), buf


class ListScriptsCommand(Command):

    command = b'LISTSCRIPTS'

    @classmethod
    def parse(cls, buf: memoryview, params: Params) \
            -> tuple[ListScriptsCommand, memoryview]:
        _, buf = EndLine.parse(buf, params)
        return cls(), buf


class SetActiveCommand(Command):

    command = b'SETACTIVE'

    def __init__(self, script_name: Optional[str]) -> None:
        super().__init__()
        self.script_name: Final = script_name

    @classmethod
    def parse(cls, buf: memoryview, params: Params) \
            -> tuple[SetActiveCommand, memoryview]:
        script_name, buf = cls._parse_script_name(buf, params, True)
        _, buf = EndLine.parse(buf, params)
        return cls(script_name or None), buf


class GetScriptCommand(Command):

    command = b'GETSCRIPT'

    def __init__(self, script_name: str) -> None:
        super().__init__()
        self.script_name: Final = script_name

    @classmethod
    def parse(cls, buf: memoryview, params: Params) \
            -> tuple[GetScriptCommand, memoryview]:
        script_name, buf = cls._parse_script_name(buf, params)
        _, buf = EndLine.parse(buf, params)
        return cls(script_name), buf


class DeleteScriptCommand(Command):

    command = b'DELETESCRIPT'

    def __init__(self, script_name: str) -> None:
        super().__init__()
        self.script_name: Final = script_name

    @classmethod
    def parse(cls, buf: memoryview, params: Params) \
            -> tuple[DeleteScriptCommand, memoryview]:
        script_name, buf = cls._parse_script_name(buf, params)
        _, buf = EndLine.parse(buf, params)
        return cls(script_name), buf


class RenameScriptCommand(Command):

    command = b'RENAMESCRIPT'

    def __init__(self, old_script_name: str, new_script_name: str) -> None:
        super().__init__()
        self.old_script_name: Final = old_script_name
        self.new_script_name: Final = new_script_name

    @classmethod
    def parse(cls, buf: memoryview, params: Params) \
            -> tuple[RenameScriptCommand, memoryview]:
        old_script_name, buf = cls._parse_script_name(buf, params)
        new_script_name, buf = cls._parse_script_name(buf, params)
        _, buf = EndLine.parse(buf, params)
        return cls(old_script_name, new_script_name), buf


class CheckScriptCommand(Command):

    command = b'CHECKSCRIPT'

    def __init__(self, script_data: bytes) -> None:
        super().__init__()
        self.script_data: Final = script_data

    @classmethod
    def parse(cls, buf: memoryview, params: Params) \
            -> tuple[CheckScriptCommand, memoryview]:
        script_data, buf = String.parse(buf, params)
        _, buf = EndLine.parse(buf, params)
        return cls(script_data.value), buf
