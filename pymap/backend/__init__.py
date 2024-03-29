
from __future__ import annotations

from ..interfaces.backend import BackendInterface
from ..plugin import Plugin

__all__ = ['backends']

#: Registers new backend plugins.
backends: Plugin[BackendInterface] = Plugin('pymap.backend')
