"""Package defining all the IMAP parsing and response classes."""

from typing import Optional

from .response import ResponseCode
from ..bytes import MaybeBytes

__all__ = ['RequiresContinuation', 'NotParseable', 'InvalidContent',
           'UnexpectedType']


class RequiresContinuation(Exception):
    """Indicates that the buffer has been successfully parsed so far, but
    requires a continuation of the command from the client.

    Args:
        message: The message from the server.
        literal_length: If the continuation is for a string literal, this is
            the byte length to expect.

    """

    __slots__ = ['message', 'literal_length']

    def __init__(self, message: bytes, literal_length: int = 0) -> None:
        super().__init__()
        self.message = message
        self.literal_length = literal_length


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
        self.buf = bytes(buf)
        self.code = ResponseCode.of(code)
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
