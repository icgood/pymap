
from __future__ import annotations

from .interfaces.backend import ServiceInterface
from .plugin import Plugin

__all__ = ['services']

#: Registers new service plugins.
services: Plugin[ServiceInterface] = Plugin('pymap.service')
