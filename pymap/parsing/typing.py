"""Defines type hints used by parseable objects."""

from typing import ByteString, SupportsBytes, Union, TypeVar

__all__ = ['MaybeBytes', 'ParseableType']

#: A bytes object or an object with a ``__bytes__`` method.
MaybeBytes = Union[ByteString, SupportsBytes]

#: The generic type parsed from a buffer.
ParseableType = TypeVar('ParseableType')
