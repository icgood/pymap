
from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, Mapping
from typing import TypeVar, Generic, Optional, Final

from pkg_resources import iter_entry_points, DistributionNotFound

__all__ = ['PluginT', 'Plugin']

#: The plugin type variable.
PluginT = TypeVar('PluginT')


class Plugin(Generic[PluginT], Iterable[tuple[str, PluginT]]):
    """Plugin system, typically loaded from :mod:`pkg_resources` `entry points
    <https://packaging.python.org/guides/creating-and-discovering-plugins/#using-package-metadata>`_.

    >>> example: Plugin[type[Example]] = Plugin('plugins.example')
    >>> example.add('two', ExampleTwo)
    >>> example.registered
    {'one': ExampleOne, 'two': ExampleTwo}

    Note:
        Plugins registered from *group* entry points are lazy-loaded. This is
        to avoid cyclic imports.

    Args:
        group: The entry point group to load.

    """

    def __init__(self, group: str) -> None:
        super().__init__()
        self.group: Final = group
        self._loaded: Optional[dict[str, PluginT]] = None
        self._added: dict[str, PluginT] = {}

    def __iter__(self) -> Iterator[tuple[str, PluginT]]:
        return iter(self.registered.items())

    @property
    def registered(self) -> Mapping[str, PluginT]:
        """A mapping of the registered plugins, keyed by name."""
        loaded = self._load()
        return {**loaded, **self._added}

    @property
    def first(self) -> PluginT:
        """The first registered plugin.

        Raises:
            IndexError

        """
        first = next(iter(self.registered.values()), None)
        if first is None:
            raise IndexError(f'No plugins registered: {self.group}')
        return first

    def _load(self) -> Mapping[str, PluginT]:
        loaded = self._loaded
        if loaded is None:
            loaded = {}
            for entry_point in iter_entry_points(self.group):
                try:
                    plugin: PluginT = entry_point.load()
                except DistributionNotFound:
                    pass  # optional dependencies not installed
                else:
                    loaded[entry_point.name] = plugin
            self._loaded = loaded
        return loaded

    def add(self, name: str, plugin: PluginT) -> None:
        """Add a new plugin by name.

        Args:
            name: The identifying name of the plugin.
            plugin: The plugin object.

        """
        self._added[name] = plugin

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
        return f'Plugin({self.group!r})'
