
from __future__ import annotations

from abc import abstractmethod
from collections.abc import Callable
from typing import Any, Protocol

__all__ = ['HealthStatusView', 'HealthStatus']

_Callback = Callable[[bool], Any]


class HealthStatusView(Protocol):
    """Exposes a view of the health status of a backend or service, without
    allowing changes to the status.

    """

    @property
    @abstractmethod
    def healthy(self) -> bool:
        """The current healthy (True) or unhealthy (False) status."""
        ...

    @abstractmethod
    def register(self, callback: _Callback) -> None:
        """Registers a callback to be called when transitioning from healthy to
        unhealthy or from unhealthy to healthy. The callback will also be
        called immediately with the current value of :attr:`.healthy`.

        Args:
            callback: Takes a single boolean argument, :attr:`.healthy`.

        """
        ...


class HealthStatus(HealthStatusView):
    """Provides a mechanism for backends or services to track their health as a
    simple boolean state: healthy or unhealthy.

    Args:
        initial: Initial value for :attr:`.healthy`.

    """

    def __init__(self, initial: bool = False) -> None:
        super().__init__()
        self._listeners: list[_Callback] = []
        self._healthy = initial

    @property
    def healthy(self) -> bool:
        return self._healthy

    def register(self, callback: _Callback) -> None:
        self._listeners.append(callback)
        callback(self._healthy)

    def set(self, healthy: bool) -> None:
        """Updates healthy or unhealthy. Registered callbacks will only be
        called if transitioning from healthy to unhealthy or vice versa.

        Args:
            healthy: The new healthy (True) or unhealthy (False) status.

        """
        prev_healthy = self._healthy
        if healthy != prev_healthy:
            self._healthy = healthy
            for listener in self._listeners:
                listener(healthy)

    def set_healthy(self) -> None:
        """Shortcut for calling :meth:`.set` with True."""
        self.set(True)

    def set_unhealthy(self) -> None:
        """Shortcut for calling :meth:`.set` with False."""
        self.set(False)
