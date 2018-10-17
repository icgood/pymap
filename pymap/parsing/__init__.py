"""Package defining all the IMAP parsing and response classes."""

import re
from typing import Tuple, Optional, Generic, Sequence, Dict, Any, List, Type

from .typing import ParseableType

__all__ = ['RequiresContinuation', 'NotParseable', 'InvalidContent',
           'UnexpectedType', 'Parseable', 'ExpectedParseable', 'Space',
           'EndLine', 'Primitive', 'Special', 'Params']


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

    def __init__(self, buf: bytes) -> None:
        super().__init__()
        self.buf = buf
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


class Params:
    """Parameters used and passed around among the :meth:`~Parseable.parse`
    methods.

    Attributes:
        continuations: The continuation buffers remaining for parsing.
        expected: The types that are expected in the next parsed object.
        list_expected: The types that are expect in a parsed list.
        uid: The next parsed command came after a ``UID`` command.
        charset: Strings should be decoded using this character set.
        tag: The next parsed command uses this tag bytestring.

    """

    __slots__ = ['continuations', 'expected', 'list_expected',
                 'uid', 'charset', 'tag']

    def __init__(self, continuations: List[bytes] = None,
                 expected: Sequence[Type['Parseable']] = None,
                 list_expected: Sequence[Type['Parseable']] = None,
                 uid: bool = False,
                 charset: str = None,
                 tag: bytes = None) -> None:
        self.continuations = continuations or []
        self.expected = expected or []
        self.list_expected = list_expected or []
        self.uid = uid
        self.charset = charset
        self.tag = tag or b'.'

    def _set_if_none(self, kwargs: Dict[str, Any], attr: str, value) -> None:
        if value is not None:
            kwargs[attr] = value
        else:
            kwargs[attr] = getattr(self, attr)

    def copy(self, continuations: Sequence['Parseable'] = None,
             expected: Sequence[Type['Parseable']] = None,
             list_expected: Sequence[Type['Parseable']] = None,
             uid: bool = None,
             charset: str = None,
             tag: bytes = None) -> 'Params':
        """Copy the parameters, possibly replacing a subset."""
        kwargs: Dict[str, Any] = {}
        self._set_if_none(kwargs, 'continuations', continuations)
        self._set_if_none(kwargs, 'expected', expected)
        self._set_if_none(kwargs, 'list_expected', list_expected)
        self._set_if_none(kwargs, 'uid', uid)
        self._set_if_none(kwargs, 'charset', charset)
        self._set_if_none(kwargs, 'tag', tag)
        return Params(**kwargs)


class Parseable(Generic[ParseableType]):
    """Represents a parseable data object from an IMAP stream. The sub-classes
    implement the different data formats.

    This base class will be inherited by all necessary entries in the IMAP
    formal syntax section.

    """

    _whitespace_pattern = re.compile(br' +')

    @property
    def value(self) -> ParseableType:
        """The primary value associated with the parsed data."""
        raise NotImplementedError

    @classmethod
    def _whitespace_length(cls, buf, start=0) -> int:
        match = cls._whitespace_pattern.match(buf, start)
        if match:
            return match.end(0) - start
        return 0

    def __bytes__(self) -> bytes:
        raise NotImplementedError

    @classmethod
    def parse(cls, buf: bytes, params: 'Params') -> Tuple['Parseable', bytes]:
        """Implemented by sub-classes to define how to parse the given buffer.

        Args:
            buf: The bytes containing the data to be parsed.
            params: The parameters used by some parseable types.

        """
        raise NotImplementedError


class ExpectedParseable(Parseable[None]):
    """Non-instantiable class, used to parse a buffer from a list of
    expected types.

    """

    def __init__(self) -> None:
        super().__init__()
        raise NotImplementedError

    @property
    def value(self) -> None:
        raise NotImplementedError

    def __bytes__(self) -> bytes:
        raise NotImplementedError

    @classmethod
    def parse(cls, buf: bytes, params: 'Params') -> Tuple['Parseable', bytes]:
        """Parses the given buffer by attempting to parse the list of
        :attr:`~Params.expected` types until one of them succeeds,
        then returns the parsed object.

        Args:
            buf: The bytes containing the data to be parsed.
            params: The parameters used by some parseable types.

        """
        for data_type in params.expected:
            try:
                return data_type.parse(buf, params)
            except NotParseable:
                pass
        raise UnexpectedType(buf)


class Space(Parseable[int]):
    """Represents at least one space character.

    Args:
        length: The number of spaces parsed.

    """

    def __init__(self, length: int) -> None:
        super().__init__()
        self.length = length

    @property
    def value(self) -> int:
        """The number of spaces parsed."""
        return self.length

    @classmethod
    def parse(cls, buf: bytes, params: 'Params') -> Tuple['Space', bytes]:
        ret = cls._whitespace_length(buf)
        if not ret:
            raise NotParseable(buf)
        return cls(ret), buf[ret:]

    def __bytes__(self) -> bytes:
        return b' ' * self.length


class EndLine(Parseable[bytes]):
    """Represents the end of a parsed line. This will only parse if the buffer
    has zero or more space characters followed by a new-line sequence.

    Args:
        preceding_spaces: The number of space characteres before the newline.
        carriage_return: Whether the newline included a carriage return.

    Attributes:
        preceding_spaces: The number of space characteres before the newline.
        carriage_return: Whether the newline included a carriage return.

    """

    _pattern = re.compile(br' *(\r?)\n')

    def __init__(self, preceding_spaces: int = 0,
                 carriage_return: bool = True) -> None:
        super().__init__()
        self.preceding_spaces = preceding_spaces
        self.carriage_return = carriage_return

    @property
    def value(self) -> bytes:
        """The endline bytestring."""
        return b'\r\n' if self.carriage_return else b'\n'

    @classmethod
    def parse(cls, buf: bytes, params: 'Params') -> Tuple['EndLine', bytes]:
        match = cls._pattern.match(buf)
        if not match:
            raise NotParseable(buf)
        preceding_spaces = match.start(1)
        carriage_return = bool(match.group(1))
        return cls(preceding_spaces, carriage_return), buf[match.end(0):]

    def __bytes__(self) -> bytes:
        return b' ' * self.preceding_spaces + self.value


class Primitive(Parseable[ParseableType]):
    """Base class for primitive data objects from an IMAP stream. The
    sub-classes implement the different primitive formats.

    """

    _atom_pattern = re.compile(br'[\x21\x23\x24\x26\x27\x2B'
                               br'-\x5B\x5E-\x7A\x7C\x7E]+')

    @property
    def value(self) -> ParseableType:
        raise NotImplementedError

    def __bytes__(self) -> bytes:
        raise NotImplementedError

    @classmethod
    def parse(cls, buf: bytes, params: 'Params') -> Tuple['Parseable', bytes]:
        raise NotImplementedError


class Special(Parseable[ParseableType]):
    """Base class for special data objects in an IMAP stream."""

    @property
    def value(self) -> ParseableType:
        raise NotImplementedError

    def __bytes__(self) -> bytes:
        raise NotImplementedError

    @classmethod
    def parse(cls, buf: bytes, params: 'Params') -> Tuple['Parseable', bytes]:
        raise NotImplementedError
