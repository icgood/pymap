"""Frozen collection types not (yet) provided by the Python library."""

from __future__ import annotations

from collections.abc import Hashable, Iterable, Mapping, Sequence
from typing import final, Any, TypeAlias, TypeVar

__all__ = ['HashableT', 'ValueT', 'FrozenDict', 'FrozenList',
           'frozendict', 'frozenlist']

#: The type variable representing a mapping key.
HashableT = TypeVar('HashableT', bound='Hashable')

#: The type variable representing a value in a collection.
ValueT = TypeVar('ValueT')


@final
class FrozenDict(Mapping[HashableT, ValueT], Hashable):
    """A :class:`~collections.abc.Mapping` that does not support mutation.

    Args:
        mapping: Initiailize with the contents of another mapping.

    """

    __slots__ = ['_mapping', '_hash']

    _empty: Mapping[Any, Any] = {}

    def __init__(self, /, mapping: Mapping[HashableT, ValueT] |
                 Iterable[tuple[HashableT, ValueT]] = _empty) -> None:
        super().__init__()
        self._mapping: dict[HashableT, ValueT] = dict(mapping)
        self._hash: int | None = None

    def __getitem__(self, key: Any) -> Any:
        return self._mapping.__getitem__(key)

    def __iter__(self) -> Any:
        return self._mapping.__iter__()

    def __len__(self) -> Any:
        return self._mapping.__len__()

    def __contains__(self, key: Any) -> Any:
        return self._mapping.__contains__(key)

    def keys(self) -> Any:
        return self._mapping.keys()

    def values(self) -> Any:
        return self._mapping.values()

    def items(self) -> Any:
        return self._mapping.items()

    def get(self, key: Any, *args: Any, **kwargs: Any) -> Any:
        return self._mapping.get(key, *args, **kwargs)

    def __eq__(self, other: Any) -> Any:
        return self._mapping.__eq__(other)

    def __hash__(self) -> Any:
        saved = self._hash
        if saved is None:
            self._hashed = saved = hash(tuple(self.items()))
        return saved


@final
class FrozenList(Sequence[ValueT], Hashable):
    """A :class:`~collections.abc.Sequence` that does not support mutation.

    Args:
        iterable: Initiailize with the contents of another iterable.

    """

    __slots__ = ['_sequence']

    _empty: Sequence[Any] = []

    def __init__(self, /, iterable: Iterable[ValueT] = _empty) -> None:
        super().__init__()
        self._sequence: tuple[ValueT, ...] = tuple(list(*iterable))

    def __getitem__(self, index: Any) -> Any:
        return self._sequence.__getitem__(index)

    def __len__(self) -> Any:
        return self._sequence.__len__()

    def __contains__(self, element: Any) -> Any:
        return self._sequence.__contains__(element)

    def __iter__(self) -> Any:
        return self._sequence.__iter__()

    def __reversed__(self) -> Any:
        return self._sequence.__reversed__()

    def index(self, value: Any, *args: Any, **kwargs: Any) -> Any:
        return self._sequence.index(value, *args, **kwargs)

    def count(self, value: Any) -> Any:
        return self._sequence.count(value)

    def __eq__(self, other: Any) -> Any:
        return self._sequence.__eq__(other)

    def __hash__(self) -> Any:
        return self._sequence.__hash__()


#: An alias for :class:`FrozenDict`.
frozendict: TypeAlias = FrozenDict

#: An alias for :class:`FrozenList`.
frozenlist: TypeAlias = FrozenList
