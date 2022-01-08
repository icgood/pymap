
from __future__ import annotations

import logging
from collections.abc import Callable
from types import MethodType
from typing import TypeAlias, Any
from weakref import finalize, ref, WeakMethod, WeakSet

__all__ = ['HealthStatus']

_log = logging.getLogger(__name__)

_Callback: TypeAlias = Callable[[bool], Any]
_WeakCallback: TypeAlias = Callable[[], _Callback | None]


class HealthStatus:
    """Provides a mechanism for backends or services to track their health as a
    simple boolean state: healthy or unhealthy.

    Args:
        initial: The initial health status.
        name: A name for the health status component.

    """

    def __init__(self, initial: bool = True, *, name: str = '') -> None:
        super().__init__()
        self._name = name
        self._listeners: set[_WeakCallback] = set()
        self._watchers: WeakSet[HealthStatus] = WeakSet()
        self._dependencies: WeakSet[HealthStatus] = WeakSet()
        self._healthy = initial
        self._prev_healthy = initial
        if name:
            self._listeners.add(lambda: self._log_change)

    @property
    def name(self) -> str:
        """The name of the health status component."""
        return self._name

    @property
    def healthy(self) -> bool:
        """The current healthy (True) or unhealthy (False) status."""
        return self._healthy and all(dep.healthy for dep in self._dependencies)

    def _log_change(self, healthy: bool) -> None:
        health_str = 'healthy' if healthy else 'unhealthy'
        _log.debug('%s is now %s', self.name, health_str)

    def register(self, callback: _Callback) -> None:
        """Registers a callback to be called when transitioning from healthy to
        unhealthy or from unhealthy to healthy. The callback will also be
        called immediately with the current value of :attr:`.healthy`.

        Args:
            callback: Takes a single boolean argument, :attr:`.healthy`.

        """
        if isinstance(callback, MethodType):
            self._listeners.add(WeakMethod(callback))
        else:
            self._listeners.add(ref(callback))
        callback(self.healthy)

    def _check(self, seen: set[HealthStatus]) -> None:
        new_healthy = self.healthy
        if new_healthy != self._prev_healthy:
            self._prev_healthy = new_healthy
            seen.add(self)
            for listener in self._listeners:
                cb = listener()
                if cb is not None:
                    cb(new_healthy)
            for watcher in self._watchers:
                if watcher not in seen:
                    watcher._check(seen)

    def new_dependency(self, initial: bool = True, *,
                       name: str = '') -> HealthStatus:
        """Adds a new health status as a dependency of this status. All
        dependencies must be :attr:`.healthy` for this status to be
        :attr:`.healthy`.

        Args:
            initial: The initial health status of the dependency.
            name: A name for the health status component.

        """
        full_name = f'{self.name}.{name}' if name else ''
        status = HealthStatus(initial, name=full_name)
        self._dependencies.add(status)
        status._watchers.add(self)
        self._check(set())
        finalize(status, self._check, set())
        return status

    def set(self, healthy: bool) -> None:
        """Updates healthy or unhealthy.

        Args:
            healthy: The new healthy (True) or unhealthy (False) status.

        """
        self._healthy = healthy
        self._check(set())

    def set_healthy(self) -> None:
        """Shortcut for calling :meth:`.set` with True."""
        self.set(True)

    def set_unhealthy(self) -> None:
        """Shortcut for calling :meth:`.set` with False."""
        self.set(False)
