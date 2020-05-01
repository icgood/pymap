
from __future__ import annotations

from typing import TypeVar, Generic, Callable, Iterable, Iterator, \
    Tuple, Mapping, Dict

from pkg_resources import iter_entry_points, DistributionNotFound

__all__ = ['PluginT', 'Plugin']

PluginT = TypeVar('PluginT')


class Plugin(Generic[PluginT], Iterable[Tuple[str, PluginT]]):
    """Plugin system, typically loaded from :mod:`pkg_resources` entry points.

    >>> example: Plugin[Type[Example]] = Plugin()
    >>> example.load('plugins.example', 'one')
    >>> example.add('two', ExampleTwo)
    >>> example.registered
    {'one': ExampleOne, 'two': ExampleTwo}

    Args:
        group: An initial group to :meth:`.load`.

    """

    def __init__(self, group: str = None) -> None:
        super().__init__()
        self._registered: Dict[str, PluginT] = {}
        if group is not None:
            self.load(group)

    def __iter__(self) -> Iterator[Tuple[str, PluginT]]:
        return iter(self._registered.items())

    @property
    def registered(self) -> Mapping[str, PluginT]:
        """A mapping of the registered plugins, keyed by name."""
        return self._registered

    def load(self, group: str, name: str = None) -> None:
        """Load an entry points group. This allows packages which are loaded
        to :meth:`.add` or :meth:`.register` new plugins.

        Args:
            group: The :mod:`pkg_resources` entry points group name.
            name: Limits loading to entry points of the given name.

        """
        for entry_point in iter_entry_points(group, name):
            try:
                plugin: PluginT = entry_point.load()
            except DistributionNotFound:
                pass  # optional dependencies not installed
            else:
                self.add(entry_point.name, plugin)

    def add(self, name: str, plugin: PluginT) -> None:
        """Add a new plugin by name.

        Args:
            name: The identifying name of the plugin.
            plugin: The plugin object.

        """
        assert name not in self._registered, \
            f'plugin {name!r} has already been registered'
        self._registered[name] = plugin

    def register(self, name: str) -> Callable[[PluginT], PluginT]:
        """Decorates a plugin implementation.

        Args:
            name: The identifying name of the plugin.

        """
        def deco(plugin: PluginT) -> PluginT:
            self.add(name, plugin)
            return plugin
        return deco
