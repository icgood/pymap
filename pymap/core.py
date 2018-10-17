"""Contains the project's version number in ``__version__``."""

import pkg_resources

__all__ = ['__version__']

#: The project version string.
__version__: str = pkg_resources.require("pymap")[0].version
