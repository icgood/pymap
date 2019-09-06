
from __future__ import annotations

from . import CommandAny, CommandNoArgs

__all__ = ['CapabilityCommand', 'LogoutCommand', 'NoOpCommand']


class CapabilityCommand(CommandNoArgs, CommandAny):
    """The ``CAPABILITY`` command lists current server capabilities."""

    command = b'CAPABILITY'


class LogoutCommand(CommandNoArgs, CommandAny):
    """The ``LOGOUT`` command ends the IMAP session."""

    command = b'LOGOUT'


class NoOpCommand(CommandNoArgs, CommandAny):
    """The ``NOOP`` command does nothing, but can be used to check for state
    changes on a selected mailbox.

    """

    command = b'NOOP'
