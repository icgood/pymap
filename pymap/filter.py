
from __future__ import annotations

from abc import abstractmethod
from collections.abc import Sequence
from typing import Optional

from .interfaces.filter import FilterValueT, FilterCompilerInterface, \
    FilterSetInterface
from .plugin import Plugin

__all__ = ['filters', 'PluginFilterSet', 'SingleFilterSet']

#: Registers filter compiler plugins.
filters: Plugin[type[FilterCompilerInterface]] = Plugin(
    'pymap.filter', default='sieve')


class PluginFilterSet(FilterSetInterface[FilterValueT]):
    """Base class for filter set implementations that use a filter compiler
    declared in the ``pymap.filter`` entry point. The declared entry points
    must sub-class :class:`FilterCompiler`.

    Args:
        plugin_name: The filter plugin name, or ``None`` for default.
        value_type: The filter value representation type.

    """

    def __init__(self, plugin_name: Optional[str],
                 value_type: type[FilterValueT]) -> None:
        super().__init__()
        self._plugin_name = plugin_name
        self._value_type = value_type
        self._compiler: Optional[FilterCompilerInterface[FilterValueT]] = None

    @property
    def compiler(self) -> FilterCompilerInterface[FilterValueT]:
        if self._compiler is None:
            name = self._plugin_name
            if name is not None:
                filter_cls = filters.registered[name]
            else:
                filter_cls = filters.default
            compiler = filter_cls()
            if not issubclass(compiler.value_type, self._value_type):
                raise TypeError(f'{filter_cls} does not support '
                                f'{self._value_type}')
            self._compiler = compiler
        return self._compiler


class SingleFilterSet(FilterSetInterface[FilterValueT]):
    """Base class for a filter set that does not use named filter
    implementations, it contains only a single active filter implementation.

    """

    @property
    def name(self) -> str:
        """The permanent name for the active filter."""
        return 'active'

    async def put(self, name: str, value: FilterValueT) -> None:
        if name == self.name:
            await self.replace_active(value)

    async def delete(self, name: str) -> None:
        if name == self.name:
            await self.replace_active(None)
        else:
            raise KeyError(name)

    async def rename(self, before_name: str, after_name: str) -> None:
        raise NotImplementedError()

    async def clear_active(self) -> None:
        raise NotImplementedError()

    async def set_active(self, name: str) -> None:
        if name != self.name:
            raise KeyError(name)

    async def get(self, name: str) -> FilterValueT:
        if name == self.name:
            value = await self.get_active()
            if value is None:
                raise KeyError(name)
            else:
                return value
        else:
            raise KeyError(name)

    async def get_all(self) -> tuple[Optional[str], Sequence[str]]:
        value = await self.get_active()
        if value is None:
            return None, []
        else:
            return self.name, [self.name]

    async def replace_active(self, value: Optional[FilterValueT]) -> None:
        """Replace the current active filter value with a new value.

        Args:
            value: The new filter value.

        """
        raise NotImplementedError()

    @abstractmethod
    async def get_active(self) -> Optional[FilterValueT]:
        ...
