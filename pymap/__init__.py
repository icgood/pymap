"""Contains the package version string.

See Also:
    `PEP 396 <https://www.python.org/dev/peps/pep-0396/>`_

"""

import pkg_resources

__all__ = ['__version__']

#: The package version string.
__version__: str = pkg_resources.require(__package__)[0].version
