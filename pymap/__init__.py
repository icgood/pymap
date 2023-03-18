"""Contains the package version string.

See Also:
    `PEP 396 <https://www.python.org/dev/peps/pep-0396/>`_

"""

from importlib.metadata import distribution

__all__ = ['__version__']

#: The package version string.
__version__: str = distribution(__package__).version
