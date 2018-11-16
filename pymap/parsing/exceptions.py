"""Package defining all the IMAP parsing and response classes."""

from typing import Optional

from .response import ResponseBad, ResponseCode
from ..bytes import MaybeBytes

__all__ = ['RequiresContinuation', 'NotParseable', 'InvalidContent',
           'UnexpectedType', 'BadCommand', 'CommandNotFound', 'CommandInvalid']


class RequiresContinuation(Exception):
    """Indicates that the buffer has been successfully parsed so far, but
    requires a continuation of the command from the client.

    Args:
        message: The message from the server.
        literal_length: If the continuation is for a string literal, this is
            the byte length to expect.

    """

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

    def __init__(self, buf: bytes, code: Optional[MaybeBytes] = None) -> None:
        super().__init__()
        self.buf = buf
        self.code = ResponseCode.of(code)
        self._raw: Optional[bytes] = None
        self._before: Optional[bytes] = None
        self._after: Optional[bytes] = None
        self.offset: int = 0
        if isinstance(buf, memoryview):
            obj = getattr(buf, 'obj')
            nbytes = getattr(buf, 'nbytes')
            self.offset = len(obj) - nbytes

    @property
    def before(self) -> bytes:
        """The bytes before the parsing error was encountered."""
        if self._before is not None:
            return self._before
        buf = self.buf
        if isinstance(buf, memoryview):
            buf = getattr(buf, 'obj')
        self._before = before = buf[0:self.offset]
        return before

    @property
    def after(self) -> bytes:
        """The bytes after the parsing error was encountered."""
        if self._after is not None:
            return self._after
        if isinstance(self.buf, memoryview):
            self._after = after = self.buf.tobytes()
        else:
            self._after = after = self.buf
        return after

    def __bytes__(self) -> bytes:
        if self._raw is not None:
            return self._raw
        before = self.before
        after = self.after.rstrip(b'\r\n')
        self._raw = raw = self.error_indicator.join((before, after))
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


class BadCommand(Exception):
    """Base class for errors that occurred while parsing a command received
    from the client.

    Args:
        tag: The command tag value.

    """

    def __init__(self, tag: bytes) -> None:
        super().__init__()
        self.tag = tag

    @property
    def code(self) -> Optional[ResponseCode]:
        """The optional response code."""
        return None

    def __bytes__(self) -> bytes:
        raise NotImplementedError

    def __str__(self) -> str:
        return bytes(self).decode('ascii', 'ignore')

    def get_response(self) -> ResponseBad:
        """The response to send back to the client in response to the command
        parsing error.

        """
        return ResponseBad(self.tag, bytes(self), self.code)


class CommandNotFound(BadCommand):
    """Error indicating the data was not parseable because the command was not
    found.

    Args:
        tag: The command tag value.
        command: The command name.

    """

    def __init__(self, tag: bytes, command: bytes = None) -> None:
        super().__init__(tag)
        self.command = command

    def __bytes__(self) -> bytes:
        if self.command:
            return b'Command Not Found: %b' % self.command
        else:
            return b'Command Not Given'


class CommandInvalid(BadCommand):
    """Error indicating the data was not parseable because the command had
    invalid arguments.

    Args:
        tag: The command tag value.
        command: The command class.

    """

    def __init__(self, tag: bytes, command: bytes) -> None:
        super().__init__(tag)
        self.command = command
        self._raw: Optional[bytes] = None

    @property
    def code(self) -> Optional[ResponseCode]:
        return self.cause.code

    @property
    def cause(self) -> NotParseable:
        """The parsing exception that caused this exception."""
        exc = self.__cause__
        if not exc or not isinstance(exc, NotParseable):
            raise TypeError('Exception must have cause')
        return exc

    def __bytes__(self) -> bytes:
        if self._raw is None:
            self._raw = b': '.join((self.command, bytes(self.cause)))
        return self._raw
