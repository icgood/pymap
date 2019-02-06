"""Defines useful types and utilities for working with bytestrings."""

import re
from abc import abstractmethod, ABCMeta
from itertools import chain
from typing import cast, Any, TypeVar, ByteString, SupportsBytes, Union, \
    Callable, Iterable, Optional, Pattern, Match
from typing_extensions import Protocol

__all__ = ['MaybeBytes', 'MaybeBytesT', 'WriteStream', 'Writeable',
           'BytesFormat', 'ReView', 'rev']

#: A bytes object, memoryview,  or an object with a ``__bytes__`` method.
MaybeBytes = Union[ByteString, memoryview, SupportsBytes]

#: A type variable bound to :class:`MaybeBytes`.
MaybeBytesT = TypeVar('MaybeBytesT', bound=MaybeBytes)

_FormatArg = Union[MaybeBytes, int]


class WriteStream(Protocol):
    """Typing protocol indicating the object implements the :meth:`.write`
    method.

    See Also:
        :class:`~asyncio.StreamWriter`, :class:`~typing.BinaryIO`

    """

    @abstractmethod
    def write(self, data: bytes) -> Any:
        """Defines an abstract method where ``data`` is written to a stream or
        buffer.

        Args:
            data: The data to write.

        """
        ...


class Writeable(metaclass=ABCMeta):
    """Base class for types that can be written to a stream."""

    @classmethod
    def empty(cls) -> 'Writeable':
        """Return a :class:`Writeable` for an empty string."""
        return _EmptyWriteable()

    @classmethod
    def wrap(cls, data: MaybeBytes) -> 'Writeable':
        """Wrap the bytes in a :class:`Writeable`.

        Args:
            data: The object to wrap.

        """
        return _WrappedWriteable(data)

    @classmethod
    def concat(cls, data: Iterable[MaybeBytes]) -> 'Writeable':
        """Wrap the iterable in a :class:`Writeable` that will write eachitem.

        Args:
            data: The iterable to wrap.

        """
        return _ConcatWriteable(data)

    def write(self, writer: WriteStream) -> None:
        """Write the object to the stream, with one or more calls to
        :meth:`~WriteStream.write`.

        Args:
            writer: The output stream.

        """
        writer.write(bytes(self))

    def __len__(self) -> int:
        return len(bytes(self))

    @abstractmethod
    def __bytes__(self) -> bytes:
        ...


class _EmptyWriteable(Writeable):

    def write(self, writer: WriteStream) -> None:
        pass

    def __bytes__(self) -> bytes:
        return b''

    def __repr__(self) -> str:
        return '<Writeable empty>'


class _WrappedWriteable(Writeable):

    __slots__ = ['data']

    def __init__(self, data: MaybeBytes) -> None:
        if isinstance(data, bytes):
            self.data = data
        else:
            self.data = bytes(data)

    def __bytes__(self) -> bytes:
        return self.data

    def __repr__(self) -> str:
        return f'<Writeable {repr(self.data)}>'


class _ConcatWriteable(Writeable):

    __slots__ = ['data']

    def __init__(self, data: Iterable[MaybeBytes]) -> None:
        self.data = list(data)

    def write(self, writer: WriteStream) -> None:
        for item in self.data:
            if isinstance(item, Writeable):
                item.write(writer)
            else:
                writer.write(bytes(item))

    def __bytes__(self) -> bytes:
        return BytesFormat(b'').join(self.data)

    def __repr__(self) -> str:
        return f'<Writeable {repr(self.data)}>'


class BytesFormat:
    """Helper utility for performing formatting operations that produce
    bytestrings. While similar to the builtin formatting and join
    operations, this class intends to provide cleaner typing.

    Args:
        how: The formatting string or join delimiter to use.

    """

    __slots__ = ['how']

    def __init__(self, how: bytes) -> None:
        super().__init__()
        self.how = how

    def __mod__(self, other: Union[_FormatArg, Iterable[_FormatArg]]) -> bytes:
        """String interpolation, shortcut for :meth:`.format`.

        Args:
            other: The data interpolated into the format string.

        """
        if isinstance(other, bytes):
            return self.format([other])
        elif hasattr(other, '__bytes__'):
            supports_bytes = cast(SupportsBytes, other)
            return self.format([bytes(supports_bytes)])
        elif hasattr(other, '__iter__'):
            items = cast(Iterable[_FormatArg], other)
            return self.format(items)
        return NotImplemented

    @classmethod
    def _fix_format_arg(cls, data: _FormatArg) -> Any:
        if isinstance(data, int):
            return data
        else:
            return bytes(data)

    def format(self, data: Iterable[_FormatArg]) -> bytes:
        """String interpolation into the format string.

        Args:
            data: The data interpolated into the format string.

        Examples:
            ::

                BytesFormat(b'Hello, %b!') % b'World'
                BytesFormat(b'%b, %b!') % (b'Hello', b'World')

        """
        fix_arg = self._fix_format_arg
        return self.how % tuple(fix_arg(item) for item in data)

    def join(self, *data: Iterable[MaybeBytes]) -> bytes:
        """Iterable join on a delimiter.

        Args:
            data: Iterable of items to join.

        Examples:
            ::

                BytesFormat(b' ').join([b'one', b'two', b'three'])

        """
        return self.how.join([bytes(item) for item in chain(*data)])


class ReView:
    """Wrap a :class:`~re.Pattern` so that it takes :class:`memoryview`
    strings.

    Note:
        This behavior is supported by :mod:`re`, but type stubs do not allow
        it. If that is ever resolved, remove this class.

    Args:
        pattern: The pattern to wrap.

    """

    def __init__(self, pattern: Pattern[bytes]) -> None:
        super().__init__()
        self._pattern = pattern

    @classmethod
    def compile(cls, pattern: bytes, *args, **kwargs) -> 'ReView':
        return cls(re.compile(pattern, *args, **kwargs))

    def match(self, string: Union[bytes, memoryview],
              *args, **kwargs) -> Optional[Match[bytes]]:
        string_b = cast(bytes, string)
        return self._pattern.match(string_b, *args, **kwargs)

    def fullmatch(self, string: Union[bytes, memoryview],
                  *args, **kwargs) -> Optional[Match[bytes]]:
        string_b = cast(bytes, string)
        return self._pattern.fullmatch(string_b, *args, **kwargs)

    def finditer(self, string: Union[bytes, memoryview],
                 *args, **kwargs) -> Iterable[Match[bytes]]:
        string_b = cast(bytes, string)
        return self._pattern.finditer(string_b, *args, **kwargs)

    def sub(self, repl: Union[bytes, Callable[[Match[bytes]], bytes]],
            string: Union[bytes, memoryview], *args, **kwargs) -> bytes:
        string_b = cast(bytes, string)
        return self._pattern.sub(repl, string_b, *args, **kwargs)


# Alias for ReView.
rev = ReView
