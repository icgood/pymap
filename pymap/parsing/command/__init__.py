from datetime import datetime
from typing import Tuple, ClassVar, NamedTuple, FrozenSet

from .. import Parseable, EndLine, Params
from ..specials import Flag, ExtensionOptions

__all__ = ['Command', 'CommandNoArgs', 'CommandAny', 'CommandAuth',
           'CommandNonAuth', 'CommandSelect', 'AppendMessage']


class Command(Parseable[bytes]):
    """Base class to represent the commands available to clients.

    Args:
        tag: The tag parsed from the beginning of the command line.

    """

    #: The command key, e.g. ``b'NOOP'``.
    command: ClassVar[bytes] = b''

    def __init__(self, tag: bytes) -> None:
        super().__init__()

        #: The tag parsed from the beginning of the command line.
        self.tag = tag

    @property
    def value(self) -> bytes:
        """The command name."""
        return self.command

    @classmethod
    def parse(cls, buf: bytes, params: Params) -> Tuple['Command', bytes]:
        raise NotImplementedError

    def __bytes__(self) -> bytes:
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

    @classmethod
    def parse(cls, buf: bytes, params: Params) -> Tuple['Command', bytes]:
        raise NotImplementedError


class CommandAuth(Command):
    """Represents a command available when the IMAP session has been
    authenticated.

    """

    @classmethod
    def parse(cls, buf: bytes, params: Params) -> Tuple['Command', bytes]:
        raise NotImplementedError


class CommandNonAuth(Command):
    """Represents a command available only when the IMAP session has not yet
    authenticated.

    """

    @classmethod
    def parse(cls, buf: bytes, params: Params) -> Tuple['Command', bytes]:
        raise NotImplementedError


class CommandSelect(CommandAuth):
    """Represents a command available only when the IMAP session has been
    authenticated and a mailbox has been selected.

    """

    @classmethod
    def parse(cls, buf: bytes, params: Params) -> Tuple['Command', bytes]:
        raise NotImplementedError


class AppendMessage(NamedTuple):
    """A single message from the APPEND command.

    Attributes:
        message: The raw message bytes.
        flag_set: The flags to assign to the message.
        when: The internal timestamp to assign to the message.
        options: The extension options in use for the message.

    """

    message: bytes
    flag_set: FrozenSet[Flag]
    when: datetime
    options: ExtensionOptions
