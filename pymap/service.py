
from __future__ import annotations

from typing import Type

from .interfaces.backend import ServiceInterface
from .plugin import Plugin

__all__ = ['services']

#: Registers new service plugins.
services: Plugin[Type[ServiceInterface]] = Plugin('pymap.service')
