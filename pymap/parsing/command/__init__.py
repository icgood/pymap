
from __future__ import annotations

from abc import abstractmethod, ABCMeta
from typing import Optional, ClassVar

from .. import Params, Parseable, EndLine

__all__ = ['Command', 'CommandNoArgs', 'CommandAny', 'CommandAuth',
           'CommandNonAuth', 'CommandSelect']


class Command(Parseable[bytes], metaclass=ABCMeta):
    """Base class to represent the commands available to clients.

    Args:
        tag: The tag parsed from the beginning of the command line.

    """

    #: The command key, e.g. ``b'NOOP'``.
    command: ClassVar[bytes] = b''

    #: If given, execution of this command is handled by the delegate command.
    delegate: ClassVar[Optional[type[Command]]] = None

    #: True if the command is part of a compound command.
    compound: ClassVar[bool] = False

    def __init__(self, tag: bytes) -> None:
        super().__init__()

        #: The tag parsed from the beginning of the command line.
        self.tag = tag

    @property
    def value(self) -> bytes:
        """The command name."""
        return self.command

    @classmethod
    @abstractmethod
    def parse(cls, buf: memoryview, params: Params) \
            -> tuple[Command, memoryview]:
        ...

    def __bytes__(self) -> bytes:
        return b' '.join((self.tag, self.command))

    def __repr__(self) -> str:
        return '<%s tag=%r>' % (type(self).__name__, self.tag)


class CommandNoArgs(Command, metaclass=ABCMeta):
    """Convenience class used to fail parsing when args are given to a command
    that expects nothing.

    """

    @classmethod
    def parse(cls, buf: memoryview, params: Params) \
            -> tuple[CommandNoArgs, memoryview]:
        _, buf = EndLine.parse(buf, params)
        return cls(params.tag), buf


class CommandAny(Command, metaclass=ABCMeta):
    """Represents a command available at any stage of the IMAP session.

    """
    pass


class CommandAuth(Command, metaclass=ABCMeta):
    """Represents a command available when the IMAP session has been
    authenticated.

    """
    pass


class CommandNonAuth(Command, metaclass=ABCMeta):
    """Represents a command available only when the IMAP session has not yet
    authenticated.

    """
    pass


class CommandSelect(CommandAuth, metaclass=ABCMeta):
    """Represents a command available only when the IMAP session has been
    authenticated and a mailbox has been selected.

    """
    pass
