"""Contains the context variables that are made available by the IMAP server to
backend implementations.

See Also:
    :mod:`contextvars`

Attributes:
    subsystem: The :class:`~pymap.concurrent.Subsystem` for concurrency
        primitives.
    current_command: The currently executing
        :class:`~pymap.parsing.command.Command`.
    socket_info: :class:`~pymap.sockinfo.SocketInfo` about the currently
        connected client.
    language_code: The language code string, e.g. ``en``.
    connection_exit: The active :class:`~contextlib.AsyncExitStack` that will
        be exited when the connection closes.

"""

from __future__ import annotations

from contextlib import AsyncExitStack
from contextvars import ContextVar

from .concurrent import Subsystem
from .parsing.command import Command
from .sockets import SocketInfo

__all__ = ['subsystem', 'current_command', 'socket_info', 'language_code',
           'connection_exit']

subsystem: ContextVar[Subsystem] = ContextVar(
    'subsystem', default=Subsystem.for_asyncio())
current_command: ContextVar[Command] = ContextVar('current_command')
socket_info: ContextVar[SocketInfo] = ContextVar('socket_info')
language_code: ContextVar[str] = ContextVar('language_code')
connection_exit: ContextVar[AsyncExitStack] = ContextVar('connection_exit')
