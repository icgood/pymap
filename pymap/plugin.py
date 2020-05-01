
from __future__ import annotations

from typing import TypeVar, Generic, Callable, Iterable, Iterator, \
    Tuple, Mapping, Dict

from pkg_resources import iter_entry_points, DistributionNotFound

__all__ = ['PluginT', 'Plugin']

#: The plugin type variable.
PluginT = TypeVar('PluginT')


class Plugin(Generic[PluginT], Iterable[Tuple[str, PluginT]]):
    """Plugin system, typically loaded from :mod:`pkg_resources` `entry points
    <https://packaging.python.org/guides/creating-and-discovering-plugins/#using-package-metadata>`_.

    >>> example: Plugin[Type[Example]] = Plugin('plugins.example')
    >>> example.add('two', ExampleTwo)
    >>> example.registered
    {'one': ExampleOne, 'two': ExampleTwo}

    Note:
        Plugins registered from *group* entry points are lazy-loaded. This is
        to avoid cyclic imports.

    Args:
        group: A entry point group to load.

    """

    def __init__(self, group: str = None) -> None:
        super().__init__()
        self._group = group
        self._registered: Dict[str, PluginT] = {}

    def __iter__(self) -> Iterator[Tuple[str, PluginT]]:
        return iter(self.registered.items())

    @property
    def registered(self) -> Mapping[str, PluginT]:
        """A mapping of the registered plugins, keyed by name."""
        self._load()
        return self._registered

    def _load(self) -> None:
        if self._group is not None:
            for entry_point in iter_entry_points(self._group):
                try:
                    plugin: PluginT = entry_point.load()
                except DistributionNotFound:
                    pass  # optional dependencies not installed
                else:
                    self.add(entry_point.name, plugin)
            self._group = None

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

    def __repr__(self) -> str:
        return f'Plugin({self._group!r})'
