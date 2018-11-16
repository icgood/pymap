"""Package defining all the IMAP parsing and response classes."""

import re
from abc import abstractmethod, ABCMeta
from typing import Tuple, Generic, TypeVar, Sequence, Dict, Any, List, Type

from .exceptions import NotParseable, UnexpectedType

__all__ = ['Params', 'Parseable', 'ExpectedParseable', 'Space', 'EndLine']

_ParseableT = TypeVar('_ParseableT')


class Params:
    """Parameters used and passed around among the :meth:`~Parseable.parse`
    methods.

    Attributes:
        continuations: The continuation buffers remaining for parsing.
        expected: The types that are expected in the next parsed object.
        list_expected: The types that are expect in a parsed list.
        command_name: The name of the command currently being parsed, if any.
        uid: The next parsed command came after a ``UID`` command.
        charset: Strings should be decoded using this character set.
        tag: The next parsed command uses this tag bytestring.
        max_append_len: The maximum allowed length of the message body to an
            ``APPEND`` command.

    """

    __slots__ = ['continuations', 'expected', 'list_expected', 'command_name',
                 'uid', 'charset', 'tag', 'max_string_len', 'max_append_len']

    def __init__(self, continuations: List[bytes] = None,
                 expected: Sequence[Type['Parseable']] = None,
                 list_expected: Sequence[Type['Parseable']] = None,
                 command_name: bytes = None,
                 uid: bool = False,
                 charset: str = None,
                 tag: bytes = None,
                 max_append_len: int = None) -> None:
        self.continuations = continuations or []
        self.expected = expected or []
        self.list_expected = list_expected or []
        self.command_name = command_name
        self.uid = uid
        self.charset = charset
        self.tag = tag or b'.'
        self.max_append_len = max_append_len

    def _set_if_none(self, kwargs: Dict[str, Any], attr: str, value) -> None:
        if value is not None:
            kwargs[attr] = value
        else:
            kwargs[attr] = getattr(self, attr)

    def copy(self, continuations: List[bytes] = None,
             expected: Sequence[Type['Parseable']] = None,
             list_expected: Sequence[Type['Parseable']] = None,
             command_name: bytes = None,
             uid: bool = None,
             charset: str = None,
             tag: bytes = None,
             max_append_len: int = None) -> 'Params':
        """Copy the parameters, possibly replacing a subset."""
        kwargs: Dict[str, Any] = {}
        self._set_if_none(kwargs, 'continuations', continuations)
        self._set_if_none(kwargs, 'expected', expected)
        self._set_if_none(kwargs, 'list_expected', list_expected)
        self._set_if_none(kwargs, 'command_name', command_name)
        self._set_if_none(kwargs, 'uid', uid)
        self._set_if_none(kwargs, 'charset', charset)
        self._set_if_none(kwargs, 'tag', tag)
        self._set_if_none(kwargs, 'max_append_len', max_append_len)
        return Params(**kwargs)


class Parseable(Generic[_ParseableT], metaclass=ABCMeta):
    """Represents a parseable data object from an IMAP stream. The sub-classes
    implement the different data formats.

    This base class will be inherited by all necessary entries in the IMAP
    formal syntax section.

    """

    _whitespace_pattern = re.compile(br' +')
    _atom_pattern = re.compile(br'[\x21\x23\x24\x26\x27\x2B'
                               br'-\x5B\x5E-\x7A\x7C\x7E]+')

    @property
    @abstractmethod
    def value(self) -> _ParseableT:
        """The primary value associated with the parsed data."""
        ...

    @classmethod
    def _whitespace_length(cls, buf: bytes, start: int = 0) -> int:
        match = cls._whitespace_pattern.match(buf, start)
        if match:
            return match.end(0) - start
        return 0

    @abstractmethod
    def __bytes__(self) -> bytes:
        ...

    def __eq__(self, other) -> bool:
        if isinstance(other, bytes):
            return bytes(self) == other
        return NotImplemented

    @classmethod
    @abstractmethod
    def parse(cls, buf: bytes, params: 'Params') -> Tuple['Parseable', bytes]:
        """Implemented by sub-classes to define how to parse the given buffer.

        Args:
            buf: The bytes containing the data to be parsed.
            params: The parameters used by some parseable types.

        """
        ...


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
