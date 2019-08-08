"""Re-exposes the :func:`re.compile` function. The typing of the arguments and
returned :class:`~typing.Pattern` are replaced such that only
:class:`bytes`-based patterns are allowed and either :class:`bytes` or
:class:`memoryview` may be used for the strings.

See Also:
    :mod:`re`

"""

import re as _re

__all__ = ['compile']


compile = _re.compile
