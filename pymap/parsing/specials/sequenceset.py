
from __future__ import annotations

from collections.abc import Iterable, Iterator, Sequence
from itertools import chain
from typing import Union, Optional

from .. import Params, Parseable, Space
from ..exceptions import NotParseable
from ...bytes import rev

__all__ = ['MaxValue', 'SequenceSet']

_SeqIdx = Union['MaxValue', int]
_SeqElem = Union[_SeqIdx, tuple[_SeqIdx, _SeqIdx]]


class MaxValue:
    """The type used as a placeholder for the maximum value."""

    def __eq__(self, other) -> bool:
        if isinstance(other, MaxValue):
            return True
        return NotImplemented

    def __hash__(self) -> int:
        return hash(type(self))


class SequenceSet(Parseable[Sequence[_SeqElem]]):
    """Represents a sequence set from an IMAP stream.

    Args:
        sequences: The sequence set data.
        uid: True if the sequences refer to message UIDs.

    Attributes:
        uid: True if the sequences refer to message UIDs.

    """

    _num_pattern = rev.compile(br'[1-9]\d*')
    _max = MaxValue()

    def __init__(self, sequences: Sequence[_SeqElem],
                 uid: bool = False) -> None:
        super().__init__()
        self.sequences = sequences
        self.uid = uid
        self._raw: Optional[bytes] = None

    @classmethod
    def all(cls, uid: bool = False) -> SequenceSet:
        """A sequence set intended to contain all values."""
        return _AllSequenceSet(uid)

    @property
    def value(self) -> Sequence[_SeqElem]:
        """The sequence set data."""
        return self.sequences

    @property
    def is_all(self) -> bool:
        """True if the sequence set starts at ``1`` and ends at the maximum
        value.

        This may be used to optimize cases of checking for a value in the set,
        avoiding the need to provide ``max_value`` in :meth:`.flatten` or
        :meth:`.iter`.

        """
        first = self.sequences[0]
        return isinstance(first, tuple) \
            and first[0] == 1 and isinstance(first[1], MaxValue)

    @classmethod
    def _get_range(cls, elem: _SeqElem, max_value: int) -> Iterable[int]:
        if isinstance(elem, int):
            if elem <= max_value:
                return range(elem, elem + 1)
            else:
                return ()
        elif isinstance(elem, MaxValue):
            return range(max_value, max_value + 1)
        else:
            left, right = elem
            if isinstance(left, MaxValue):
                left = max_value
            if isinstance(right, MaxValue):
                right = max_value
            low = min(left, right)
            if low <= max_value:
                high = min(max(left, right), max_value)
                return range(low, high + 1)
            else:
                return ()

    def flatten(self, max_value: int) -> frozenset[int]:
        """Return a set of all values contained in the sequence set.

        Args:
            max_value: The maximum value, in place of any ``*``.

        """
        return frozenset(self.iter(max_value))

    def iter(self, max_value: int) -> Iterator[int]:
        """Iterates through the sequence numbers contained in the set, bounded
        by the given maximum value (in place of any ``*``).

        Args:
            max_value: The maximum value of the set.

        """
        return chain.from_iterable(
            (self._get_range(elem, max_value) for elem in self.sequences))

    def _elem_bytes(self, elem: _SeqIdx) -> bytes:
        if isinstance(elem, MaxValue):
            return b'*'
        else:
            return b'%d' % elem

    def __bytes__(self) -> bytes:
        if self._raw is not None:
            return self._raw
        parts = []
        for group in self.value:
            if isinstance(group, tuple):
                left = self._elem_bytes(group[0])
                right = self._elem_bytes(group[1])
                parts.append(b'%b:%b' % (left, right))
            else:
                parts.append(self._elem_bytes(group))
        self._raw = raw = b','.join(parts)
        return raw

    def __eq__(self, other) -> bool:
        if isinstance(other, SequenceSet):
            return self.uid == other.uid \
                and self.sequences == other.sequences
        return super().__eq__(other)

    def __hash__(self) -> int:
        return hash((type(self), tuple(self.sequences), self.uid))

    def __repr__(self) -> str:
        attr = 'uidset' if self.uid else 'set'
        return '<SequenceSet %s=%r>' % (attr, self.sequences)

    @classmethod
    def _parse_part(cls, buf: memoryview) -> tuple[_SeqElem, memoryview]:
        if buf and buf[0] == 0x2a:
            item1: _SeqIdx = cls._max
            buf = buf[1:]
        else:
            match = cls._num_pattern.match(buf)
            if match:
                buf = buf[match.end(0):]
                item1 = int(match.group(0))
            else:
                raise NotParseable(buf)
        if buf and buf[0] == 0x3a:
            buf = buf[1:]
            if buf and buf[0] == 0x2a:
                return (item1, cls._max), buf[1:]
            match = cls._num_pattern.match(buf)
            if match:
                buf = buf[match.end(0):]
                return (item1, int(match.group(0))), buf
            raise NotParseable(buf)
        return item1, buf

    @classmethod
    def build(cls, seqs: Iterable[int], uid: bool = False) -> SequenceSet:
        """Build a new sequence set that contains the given values using as
        few groups as possible.

        Args:
            seqs: The sequence values to build.
            uid: True if the sequences refer to message UIDs.

        """
        seqs_list = sorted(set(seqs))
        groups: list[Union[int, tuple[int, int]]] = []
        group: Union[int, tuple[int, int]] = seqs_list[0]
        for i in range(1, len(seqs_list)):
            group_i = seqs_list[i]
            if isinstance(group, int):
                if group_i == group + 1:
                    group = (group, group_i)
                else:
                    groups.append(group)
                    group = group_i
            elif isinstance(group, tuple):
                if group_i == group[1] + 1:
                    group = (group[0], group_i)
                else:
                    groups.append(group)
                    group = group_i
        groups.append(group)
        return SequenceSet(groups, uid)

    @classmethod
    def parse(cls, buf: memoryview, params: Params) \
            -> tuple[SequenceSet, memoryview]:
        try:
            _, buf = Space.parse(buf, params)
        except NotParseable:
            pass
        sequences = []
        while buf:
            item, buf = cls._parse_part(buf)
            sequences.append(item)
            if buf and buf[0] != 0x2c:
                break
            buf = buf[1:]
        if not sequences:
            raise NotParseable(buf)
        return cls(sequences, uid=params.uid), buf


class _AllSequenceSet(SequenceSet):

    def __init__(self, uid: bool) -> None:
        super().__init__([(1, self._max)], uid)

    def iter(self, max_value: int) -> Iterator[int]:
        return iter(range(1, max_value + 1))

    def __bytes__(self) -> bytes:
        return b'1:*'

    def __repr__(self) -> str:
        return '<SequenceSet set=all>'
