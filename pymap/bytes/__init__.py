"""Defines useful types and utilities for working with bytestrings."""

from __future__ import annotations

import zlib
from abc import abstractmethod, ABCMeta
from collections.abc import Iterable, Sequence
from io import BytesIO
from itertools import chain
from numbers import Number
from typing import final, Any, Final, TypeAlias, TypeVar, TypeGuard, \
    SupportsBytes, SupportsIndex, Protocol

__all__ = ['MaybeBytes', 'MaybeBytesT', 'has_bytes', 'WriteStream',
           'Writeable', 'BytesFormat']

#: An object that can be converted to a bytestring.
MaybeBytes: TypeAlias = bytes | SupportsBytes

#: A type variable bound to :class:`MaybeBytes`.
MaybeBytesT = TypeVar('MaybeBytesT', bound=MaybeBytes)

_FormatArg: TypeAlias = SupportsIndex | MaybeBytes


def has_bytes(value: object) -> TypeGuard[MaybeBytes]:
    """Checks if the *value* is :class:`bytes` or implements the ``__bytes__``
    method to be converted to bytes.

    Args:
        value: The value to check.

    """
    return isinstance(value, bytes) or isinstance(value, SupportsBytes)


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


class HashStream(WriteStream):
    """A stream that a :class:`Writeable` can use to generate a
    non-cryptographic hash using :func:`zlib.adler32`.

    """

    __slots__ = ['_digest']

    def __init__(self) -> None:
        super().__init__()
        self._digest = zlib.adler32(b'')

    def write(self, data: bytes) -> None:
        self._digest = zlib.adler32(data, self._digest)

    def digest(self, data: Writeable | None = None) -> bytes:
        """Return the digest of the data written to the hash stream.

        Args:
            data: The data to write before computing the digest.

        """
        if data is not None:
            data.write(self)
        return self._digest.to_bytes(4, 'big')


class Writeable(metaclass=ABCMeta):
    """Base class for types that can be written to a stream."""

    __slots__: Sequence[str] = []

    @final
    def tobytes(self) -> bytes:
        """Convert the writeable object back into a bytestring using the
        :meth:`.write` method.

        """
        writer = BytesIO()
        self.write(writer)
        return writer.getvalue()

    @classmethod
    def empty(cls) -> Writeable:
        """Return a :class:`Writeable` for an empty string."""
        return _EmptyWriteable()

    @classmethod
    def wrap(cls, data: MaybeBytes) -> Writeable:
        """Wrap the bytes in a :class:`Writeable`.

        Args:
            data: The object to wrap.

        """
        return _WrappedWriteable(data)

    @classmethod
    def concat(cls, data: Iterable[MaybeBytes]) -> Writeable:
        """Wrap the iterable in a :class:`Writeable` that will write each item.

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

    def __bool__(self) -> bool:
        return True

    def __len__(self) -> int:
        return len(bytes(self))

    @abstractmethod
    def __bytes__(self) -> bytes:
        ...

    def __str__(self) -> str:
        return str(bytes(self), 'utf-8', 'replace')


class _EmptyWriteable(Writeable):

    __slots__: Sequence[str] = []

    def write(self, writer: WriteStream) -> None:
        pass

    def __bytes__(self) -> bytes:
        return b''

    def __repr__(self) -> str:
        return '<Writeable empty>'


class _WrappedWriteable(Writeable):

    __slots__ = ['data']

    def __init__(self, data: MaybeBytes) -> None:
        self.data = bytes(data)

    def __bytes__(self) -> bytes:
        return self.data

    def __repr__(self) -> str:
        return f'<Writeable {self.data!r}>'


class _ConcatWriteable(Writeable):

    __slots__ = ['data']

    def __init__(self, data: Iterable[MaybeBytes]) -> None:
        self.data = [self._wrap(val) for val in data]

    @classmethod
    def _wrap(cls, val: MaybeBytes) -> Writeable:
        if isinstance(val, Writeable):
            return val
        else:
            return _WrappedWriteable(val)

    def write(self, writer: WriteStream) -> None:
        for item in self.data:
            item.write(writer)

    def __bytes__(self) -> bytes:
        return BytesFormat(b'').join(self.data)

    def __str__(self) -> str:
        return ''.join(str(d) for d in self.data)

    def __repr__(self) -> str:
        return f'<Writeable {self.data!r}>'


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
        self.how: Final = how

    def __mod__(self, other: _FormatArg | Iterable[_FormatArg]) -> bytes:
        """String interpolation, shortcut for :meth:`.format`.

        Args:
            other: The data interpolated into the format string.

        """
        if isinstance(other, SupportsIndex) or has_bytes(other):
            return self.format([other])
        elif self._iter_guard(other):
            return self.format(other)
        raise NotImplementedError()

    @classmethod
    def _iter_guard(cls, other: _FormatArg | Iterable[_FormatArg]) \
            -> TypeGuard[Iterable[_FormatArg]]:
        return isinstance(other, Iterable)

    @classmethod
    def _fix_format_arg(cls, data: _FormatArg) -> _FormatArg:
        if isinstance(data, Number):
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

    @classmethod
    def _fix_join_arg(cls, data: _FormatArg) -> bytes:
        if isinstance(data, Number):
            return str(data).encode('ascii')
        else:
            return bytes(data)

    def join(self, *data: Iterable[_FormatArg]) -> bytes:
        """Iterable join on a delimiter.

        Args:
            data: Iterable of items to join.

        Examples:
            ::

                BytesFormat(b' ').join([b'one', b'two', b'three'])

        """
        fix_arg = self._fix_join_arg
        return self.how.join(fix_arg(item) for item in chain(*data))
