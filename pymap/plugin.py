
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
    {'one': <class 'examples.ExampleOne'>,
     'two': <class 'examples.ExampleTwo'>}

    Note:
        Plugins registered from *group* entry points are lazy-loaded. This is
        to avoid cyclic imports.

    Args:
        group: The entry point group to load.

    """

    def __init__(self, group: str, *, default: str = None) -> None:
        super().__init__()
        self.group: Final = group
        self._default = default
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
    def default(self) -> PluginT:
        """The default plugin implementation.

        This property may also be assigned a new string value to change the
        name of the default plugin.

        >>> example: Plugin[type[Example]] = Plugin('plugins.example',
        ...                                         default='one')
        >>> example.default
        <class 'examples.ExampleOne'>
        >>> example.default = 'two'
        >>> example.default
        <class 'examples.ExampleTwo'>

        Raises:
            KeyError: The default plugin name was not registered.

        """
        if self._default is None:
            raise KeyError(f'{self.group!r} has no default plugin')
        else:
            return self.registered[self._default]

    @default.setter
    def default(self, default: Optional[str]) -> None:
        self._default = default

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
