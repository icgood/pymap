
from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, Mapping
from importlib.metadata import entry_points
from typing import TypeVar, Generic, Final

__all__ = ['PluginT', 'Plugin']

#: The plugin type variable.
PluginT = TypeVar('PluginT')


class Plugin(Generic[PluginT], Iterable[tuple[str, type[PluginT]]]):
    """Plugin system, typically loaded from :mod:`importlib.metadata`
    `entry points
    <https://packaging.python.org/guides/creating-and-discovering-plugins/#using-package-metadata>`_.

    >>> example: Plugin[Example] = Plugin('plugins.example')
    >>> example.add('two', ExampleTwo)
    >>> example.registered
    {'one': <class 'examples.ExampleOne'>,
     'two': <class 'examples.ExampleTwo'>}

    Note:
        Plugins registered from *group* entry points are lazy-loaded. This is
        to avoid cyclic imports.

    Args:
        group: The entry point group to load.
        default: The name of the :attr:`.default` plugin.

    """

    def __init__(self, group: str, *, default: str | None = None) -> None:
        super().__init__()
        self.group: Final = group
        self._default = default
        self._loaded: dict[str, type[PluginT]] | None = None
        self._added: dict[str, type[PluginT]] = {}

    def __iter__(self) -> Iterator[tuple[str, type[PluginT]]]:
        return iter(self.registered.items())

    @property
    def registered(self) -> Mapping[str, type[PluginT]]:
        """A mapping of the registered plugins, keyed by name."""
        loaded = self._load()
        return {**loaded, **self._added}

    @property
    def default(self) -> type[PluginT]:
        """The default plugin implementation.

        This property may also be assigned a new string value to change the
        name of the default plugin.

        >>> example: Plugin[Example] = Plugin('plugins.example', default='one')
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
    def default(self, default: str | None) -> None:
        self._default = default

    def _load(self) -> Mapping[str, type[PluginT]]:
        loaded = self._loaded
        if loaded is None:
            loaded = {}
            for entry_point in entry_points(group=self.group):
                plugin: type[PluginT] = entry_point.load()
                loaded[entry_point.name] = plugin
            self._loaded = loaded
        return loaded

    def add(self, name: str, plugin: type[PluginT]) -> None:
        """Add a new plugin by name.

        Args:
            name: The identifying name of the plugin.
            plugin: The plugin object.

        """
        self._added[name] = plugin

    def register(self, name: str) -> Callable[[type[PluginT]], type[PluginT]]:
        """Decorates a plugin implementation.

        Args:
            name: The identifying name of the plugin.

        """
        def deco(plugin: type[PluginT]) -> type[PluginT]:
            self.add(name, plugin)
            return plugin
        return deco

    def __repr__(self) -> str:
        return f'Plugin({self.group!r})'
