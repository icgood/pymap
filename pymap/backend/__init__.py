
from __future__ import annotations

from typing import Type

from ..interfaces.backend import BackendInterface
from ..plugin import Plugin

__all__ = ['backends']

#: Registers new backend plugins.
backends: Plugin[Type[BackendInterface]] = Plugin('pymap.backend')
