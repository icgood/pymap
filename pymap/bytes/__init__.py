"""Defines useful types and utilities for working with bytestrings."""

from __future__ import annotations

from abc import abstractmethod, ABCMeta
from collections.abc import Iterable, Sequence
from io import BytesIO
from itertools import chain
from typing import cast, final, Any, Final, TypeVar, SupportsBytes, Union, \
    Protocol

__all__ = ['MaybeBytes', 'MaybeBytesT', 'WriteStream', 'Writeable',
           'BytesFormat']

#: A bytes object, memoryview,  or an object with a ``__bytes__`` method.
MaybeBytes = Union[bytes, bytearray, memoryview, SupportsBytes]

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


class HashStream(WriteStream):
    """A stream that a :class:`Writeable` can use to generate a secure hash,
    using a hash algorithm as returned by a :mod:`hashlib` constructor.

    Args:
        algo: The hash algorithm object.

    """

    __slots__ = ['_algo']

    def __init__(self, algo: Any) -> None:
        super().__init__()
        self._algo = algo

    def write(self, data: bytes) -> None:
        self._algo.update(data)

    def digest(self, data: Writeable = None) -> bytes:
        """Return the digest of the data written to the hash stream.

        Args:
            data: The data to write before computing the digest.

        """
        if data is not None:
            data.write(self)
        return self._algo.digest()


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
        self.how: Final = how

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

    @classmethod
    def _fix_join_arg(cls, data: _FormatArg) -> Any:
        if isinstance(data, int):
            return b'%d' % data
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
