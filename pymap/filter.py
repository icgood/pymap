
from __future__ import annotations

from abc import abstractmethod
from typing import Type, Optional, Tuple, Sequence

from pkg_resources import iter_entry_points, DistributionNotFound

from .interfaces.filter import FilterValueT, FilterCompilerInterface, \
    FilterSetInterface

__all__ = ['EntryPointFilterSet', 'SingleFilterSet']


class EntryPointFilterSet(FilterSetInterface[FilterValueT]):
    """Base class for filter set implementations that use a filter compiler
    declared in the ``pymap.filter`` entry point. The declared entry points
    must sub-class :class:`FilterCompiler`.

    Args:
        entry_point: The entry point name.
        group: The entry point group.

    """

    def __init__(self, entry_point: str, value_type: Type[FilterValueT], *,
                 group: str = 'pymap.filter') -> None:
        super().__init__()
        self._group = group
        self._entry_point = entry_point
        self._value_type = value_type
        self._compiler: Optional[FilterCompilerInterface[FilterValueT]] = None

    @property
    def compiler(self) -> FilterCompilerInterface[FilterValueT]:
        if self._compiler is None:
            filter_cls: Optional[Type[FilterCompilerInterface]] = None
            name = self._entry_point
            for entry_point in iter_entry_points(self._group, name):
                try:
                    filter_cls = entry_point.load()
                except DistributionNotFound:
                    pass  # optional dependencies not installed
            if filter_cls is None:
                raise LookupError(f'{self._group}:{name}')
            compiler = filter_cls()
            if not issubclass(compiler.value_type, self._value_type):
                raise TypeError(f'{self._group}:{name} does not support '
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

    async def get_all(self) -> Tuple[Optional[str], Sequence[str]]:
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
