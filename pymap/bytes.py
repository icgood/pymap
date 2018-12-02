"""Defines useful types and utilities for working with bytestrings."""

from itertools import chain
from typing import cast, TypeVar, ByteString, SupportsBytes, Union, Iterable

__all__ = ['MaybeBytes', 'MaybeBytesT', 'as_memoryview', 'BytesFormat']

#: A bytes object or an object with a ``__bytes__`` method.
MaybeBytes = Union[ByteString, SupportsBytes]

#: A type variable bound to :class:`MaybeBytes`.
MaybeBytesT = TypeVar('MaybeBytesT', bound=MaybeBytes)


def as_memoryview(val: bytes) -> bytes:
    """Wrap a bytestring in a :class:`memoryview` for performance, while
    maintaining ``bytes`` type annotation.

    Note:
        This is necessary because even though the :class:`~typing.ByteString`
        state that ``bytes`` may be used to annotate memoryview objects, it
        does not appear to work in practice. If/when this is resolved, remove
        this function in factor of a simple ``... = memoryview(val)`` call.

    See Also:
        `python/mypy#4871 <https://github.com/python/mypy/issues/4871>`_

    """
    return cast(bytes, memoryview(val))


class BytesFormat:
    """Helper utility for performing formatting operations that produce
    bytestrings. While similar to the builtin formatting and join
    operations, this class intends to provide cleaner typing.

    Args:
        how: The formatting string or join delimiter to use.

    """

    def __init__(self, how: bytes) -> None:
        super().__init__()
        self.how = how

    def __mod__(self, other: Union[MaybeBytes, Iterable[MaybeBytes]]) -> bytes:
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
            items = cast(Iterable[MaybeBytes], other)
            return self.format([bytes(item) for item in items])
        return NotImplemented

    def format(self, data: Iterable[MaybeBytes]) -> bytes:
        """String interpolation into the format string.

        Args:
            data: The data interpolated into the format string.

        Examples:
            ::

                BytesFormat(b'Hello, %b!') % b'World'
                BytesFormat(b'%b, %b!') % (b'Hello', b'World')

        """
        return self.how % tuple(bytes(item) for item in data)

    def join(self, *data: Iterable[MaybeBytes]) -> bytes:
        """Iterable join on a delimiter.

        Args:
            data: Iterable of items to join.

        Examples:
            ::

                BytesFormat(b' ').join([b'one', b'two', b'three'])

        """
        return self.how.join([bytes(item) for item in chain(*data)])
