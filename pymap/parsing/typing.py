"""Defines type hints used by parseable objects."""

from typing import SupportsBytes, Union, TypeVar

__all__ = ['MaybeBytes', 'ParseableType', 'ParseableListType']

#: A bytes object or an object with a ``__bytes__`` method.
MaybeBytes = Union[bytes, SupportsBytes]

#: The generic type parsed from a buffer.
ParseableType = TypeVar('ParseableType')

#: The generic type parsed from a list primitive.
ParseableListType = TypeVar('ParseableListType', bound=MaybeBytes)
