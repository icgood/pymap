
from __future__ import annotations

import socket as _socket
from abc import abstractmethod, ABCMeta
from asyncio import BaseTransport, StreamWriter
from collections.abc import Mapping, Sequence
from typing import Any, Union, Optional

try:
    import systemd.daemon
except ImportError as exc:
    systemd_import_exc: Optional[ImportError] = exc
else:
    systemd_import_exc = None

__all__ = ['InheritedSockets']

_Transport = Union[BaseTransport, StreamWriter]
_PeerName = Union[tuple[str, int], tuple[str, int, int, int], str]
_PeerCert = Mapping[str, Any]  # {'issuer': ..., ...}


class InheritedSockets(metaclass=ABCMeta):
    """Abstracts the ability to retrieve inherited sockets from the calling
    process, usually a service management framework.

    """

    @abstractmethod
    def get(self) -> Sequence[_socket.socket]:
        """Return the sockets inherited by the process."""
        ...

    @classmethod
    def supports(cls, service_manager: str) -> bool:
        """Return True if the given service manager is supported. This does not
        guarantee the service manager will provide inherited sockets, only that
        it is available to :meth:`.of`.

        Args:
            service_manager: The service manager name.

        """
        if service_manager == 'systemd':
            return systemd_import_exc is None
        else:
            return False

    @classmethod
    def of(cls, service_manager: str) -> InheritedSockets:
        """Return the inherited sockets for the given service manager.

        Note:
            Only ``'systemd'`` is implemented at this time.

        Args:
            service_manager: The service manager name.

        """
        if service_manager == 'systemd':
            return cls.for_systemd()
        else:
            raise KeyError(service_manager)

    @classmethod
    def for_systemd(cls) -> InheritedSockets:
        """Return the inherited sockets for `systemd`_. The `python-systemd`_
        library must be installed.

        See Also:
            `systemd.socket`_, `sd_listen_fds`_

        .. _systemd: https://freedesktop.org/wiki/Software/systemd/
        .. _systemd.socket: https://www.freedesktop.org/software/systemd/man/systemd.socket.html
        .. _sd_listen_fds: https://www.freedesktop.org/software/systemd/man/sd_listen_fds.html
        .. _python-systemd: https://github.com/systemd/python-systemd

        Raises:
            :exc:`NotImplementedError`

        """  # noqa: E501
        if systemd_import_exc:
            raise systemd_import_exc
        return _SystemdSockets()


class _SystemdSockets(InheritedSockets):

    def __init__(self) -> None:
        super().__init__()
        fds: Sequence[int] = systemd.daemon.listen_fds()
        sockets: list[_socket.socket] = []
        for fd in fds:
            family = self._get_family(fd)
            sock = _socket.fromfd(fd, family, _socket.SOCK_STREAM)
            sockets.append(sock)
        self._sockets = sockets

    def get(self) -> Sequence[_socket.socket]:
        return self._sockets

    @classmethod
    def _get_family(cls, fd: int) -> int:
        if systemd.daemon.is_socket(fd, _socket.AF_UNIX):
            return _socket.AF_UNIX
        elif systemd.daemon.is_socket(fd, _socket.AF_INET6):
            return _socket.AF_INET6
        else:
            return _socket.AF_INET
