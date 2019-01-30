
from abc import abstractmethod
from typing import Generic, Type, Optional, Tuple, Sequence

from pkg_resources import iter_entry_points, DistributionNotFound

from .interfaces.filter import FilterValueT, FilterInterface, \
    FilterSetInterface

__all__ = ['FilterCompiler', 'EntryPointFilterSet', 'SingleFilterSet']


class FilterCompiler(Generic[FilterValueT]):
    """Abstract base class for classes which can compile a filter value into an
    implementation.

    """

    @abstractmethod
    async def compile(self, value: FilterValueT) -> FilterInterface:
        """Compile the filter value and return the resulting implementation.

        Args:
            value: The filter value.

        """
        ...


class EntryPointFilterSet(FilterSetInterface[FilterValueT]):
    """Base class for filter set implementations that use a filter compiler
    declared in the ``pymap.filter`` entry point. The declared entry points
    must sub-class :class:`FilterCompiler`.

    Args:
        entry_point: The entry point name.
        group: The entry point group.

    """

    def __init__(self, entry_point: str, *,
                 group: str = 'pymap.filter') -> None:
        super().__init__()
        self._group = group
        self._entry_point = entry_point
        self._filter_compiler: Optional[FilterCompiler] = None

    @property
    def filter_compiler(self) -> FilterCompiler:
        if self._filter_compiler is None:
            filter_cls: Optional[Type[FilterCompiler]] = None
            name = self._entry_point
            for entry_point in iter_entry_points(self._group, name):
                try:
                    filter_cls = entry_point.load()
                except DistributionNotFound:
                    pass  # optional dependencies not installed
            if filter_cls is None:
                raise LookupError(f'{self._group}:{name}')
            self._filter_compiler = filter_cls()
        return self._filter_compiler

    async def compile(self, value: FilterValueT) -> FilterInterface:
        return await self.filter_compiler.compile(value)


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

    async def set_active(self, name: Optional[str]) -> None:
        if name is None:
            await self.replace_active(None)
        elif name != self.name:
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
