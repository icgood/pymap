
from abc import abstractmethod, ABCMeta
from typing import TypeVar, Generic, Callable, Optional, NoReturn

from pkg_resources import iter_entry_points, DistributionNotFound

from .interfaces.filter import FilterInterface, FilterSetInterface

__all__ = ['FilterValueT', 'EntryPointFilterSet', 'SingleFilterSet']

#: Type variable for the value used to instantiate an
#: :class:`EntryPointFilter`.
FilterValueT = TypeVar('FilterValueT')

_FilterFactory = Callable[[FilterValueT], FilterInterface]


class EntryPointFilterSet(Generic[FilterValueT], FilterSetInterface,
                          metaclass=ABCMeta):
    """Base class for filter set implementations that use a filter
    implementation declared in the ``pymap.filter`` entry point.

    The entry points should be classes or callable factories that take a single
    value and return a filter instance.

    """

    @property
    @abstractmethod
    def entry_point(self) -> str:
        """The name of the ``pymap.filter`` entry point used to implement the
        filter.

        If the entry point is found, it must implement :class:`FilterInterface`
        for the filter value type. If the entry point is not found, no filter
        is applied to new messages.

        """
        ...

    def get_filter(self, value: FilterValueT) -> FilterInterface:
        """Find the filter implementation, and return an instance of it with
        the given filter value.

        Args:
            value: The filter value.

        Raises:
            :class:`LookupError`

        """
        filter_factory: Optional[_FilterFactory] = None
        name = self.entry_point
        for entry_point in iter_entry_points('pymap.filter', name):
            try:
                filter_factory = entry_point.load()
            except DistributionNotFound:
                pass  # optional dependencies not installed
        if filter_factory is None:
            raise LookupError(name)
        return filter_factory(value)


class SingleFilterSet(FilterSetInterface, metaclass=ABCMeta):
    """Base class for a filter set that does not use named filter
    implementations, it contains only a single active filter implementation.

    """

    async def put(self, name: str, value: FilterInterface,
                  check: bool = False) -> NoReturn:
        raise NotImplementedError()

    async def delete(self, name: str) -> NoReturn:
        raise NotImplementedError()

    async def rename(self, before_name: str, after_name: str) -> NoReturn:
        raise NotImplementedError()

    async def set_active(self, name: Optional[str]) -> NoReturn:
        raise NotImplementedError()

    async def get(self, name: str) -> NoReturn:
        raise NotImplementedError()

    @abstractmethod
    async def get_active(self) -> Optional[FilterInterface]:
        ...

    async def get_all(self) -> NoReturn:
        raise NotImplementedError()
