"""Contains the context variables that are made available by the IMAP server to
backend implementations.

See Also:
    :mod:`contextvars`

"""

from __future__ import annotations

from contextlib import AsyncExitStack
from contextvars import ContextVar

from proxyprotocol.sock import SocketInfo

from .cluster import ClusterMetadata
from .concurrent import Subsystem
from .parsing.command import Command

__all__ = ['subsystem', 'current_command', 'socket_info', 'language_code',
           'connection_exit', 'cluster_metadata']

#: The :class:`~pymap.concurrent.Subsystem` for concurrency primitives.
subsystem: ContextVar[Subsystem] = ContextVar(
    'subsystem', default=Subsystem.for_asyncio())

#: The currently executing :class:`~pymap.parsing.command.Command`.
current_command: ContextVar[Command] = ContextVar('current_command')

#: :class:`~proxyprotocol.sock.SocketInfo` about the currently connected
#: client.
socket_info: ContextVar[SocketInfo] = ContextVar('socket_info')

#: The language code string, e.g. ``en``.
language_code: ContextVar[str] = ContextVar('language_code')

#: The active :class:`~contextlib.AsyncExitStack` that will be exited when the
#: connection closes.
connection_exit: ContextVar[AsyncExitStack] = ContextVar('connection_exit')

#: Manages local cluster metadata updates and access to remote status and
#: metadata.
cluster_metadata: ContextVar[ClusterMetadata] = ContextVar(
    'cluster_metdata', default=ClusterMetadata())
