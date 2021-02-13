
from __future__ import annotations

from typing import Optional, Final

from .response import ResponseCode
from ..bytes import MaybeBytes

__all__ = ['NotParseable', 'InvalidContent', 'UnexpectedType']


class NotParseable(Exception):
    """Indicates that the given buffer was not parseable by one or all of the
    data formats.

    Args:
        buf: The buffer with the parsing error.

    """

    error_indicator = b'[:ERROR:]'

    __slots__ = ['buf', 'code', '_raw']

    def __init__(self, buf: memoryview, code:
                 Optional[MaybeBytes] = None) -> None:
        super().__init__()
        self.buf: Final = bytes(buf)
        self.code: Final = ResponseCode.of(code)
        self._raw: Optional[bytes] = None

    def __bytes__(self) -> bytes:
        if self._raw is not None:
            return self._raw
        self._raw = raw = self.error_indicator.join((b'', self.buf))
        return raw

    def __str__(self) -> str:
        return str(bytes(self), 'ascii', 'replace')


class InvalidContent(NotParseable, ValueError):
    """Indicates the type of the parsed content was correct, but something
    about the content did not fit what was expected by the special type.

    """
    pass


class UnexpectedType(NotParseable):
    """Indicates that a generic parseable that was given a sub-type expectation
    failed to meet that expectation.

    """
    pass
