
from __future__ import annotations

from typing import TypeVar, Generic, Callable, Iterable, Iterator, \
    Tuple, Mapping, Dict
from typing_extensions import Final

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
        group: The entry point group to load.

    """

    def __init__(self, group: str) -> None:
        super().__init__()
        self.group: Final = group
        self._loaded = False
        self._registered: Dict[str, PluginT] = {}

    def __iter__(self) -> Iterator[Tuple[str, PluginT]]:
        return iter(self.registered.items())

    @property
    def registered(self) -> Mapping[str, PluginT]:
        """A mapping of the registered plugins, keyed by name."""
        self._load()
        return self._registered

    @property
    def first(self) -> PluginT:
        """The first registered plugin."""
        first = next(iter(self.registered.values()), None)
        assert first is not None, \
            f'plugin group {self.group} has no entries'
        return first

    def _load(self) -> None:
        if not self._loaded:
            for entry_point in iter_entry_points(self.group):
                try:
                    plugin: PluginT = entry_point.load()
                except DistributionNotFound:
                    pass  # optional dependencies not installed
                else:
                    self.add(entry_point.name, plugin)
            self._loaded = True

    def add(self, name: str, plugin: PluginT) -> None:
        """Add a new plugin by name.

        Args:
            name: The identifying name of the plugin.
            plugin: The plugin object.

        """
        assert name not in self._registered, \
            f'plugin {self.group}:{name} has already been registered'
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
        return f'Plugin({self.group!r})'
