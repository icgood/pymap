"""Contains the context variables that are made available by the IMAP server to
backend implementations.

Attributes:
    current_command: The currently executing command.
    socket_info: Info about the currently connected socket.

"""

from contextvars import ContextVar

from .parsing.command import Command
from .sockinfo import SocketInfo

__all__ = ['current_command', 'socket_info']

current_command: ContextVar[Command] = ContextVar('current_command')
socket_info: ContextVar[SocketInfo] = ContextVar('socket_info')
