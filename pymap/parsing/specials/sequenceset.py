import heapq
import math
import re
from itertools import chain
from typing import Iterable, Tuple, Union, Sequence, Optional, List

from .. import Params, Parseable, Space
from ..exceptions import NotParseable

__all__ = ['SequenceSet']

_SeqIdx = Union[None, str, int]
_SeqElem = Union[_SeqIdx, Tuple[_SeqIdx, _SeqIdx]]


class SequenceSet(Parseable[Sequence[_SeqElem]]):
    """Represents a sequence set from an IMAP stream.

    Args:
        sequences: The sequence set data.
        uid: True if the sequences refer to message UIDs.

    Attributes:
        uid: True if the sequences refer to message UIDs.

    """

    _num_pattern = re.compile(br'[1-9]\d*')

    def __init__(self, sequences: Sequence[_SeqElem],
                 uid: bool = False) -> None:
        super().__init__()
        self.sequences = sequences
        self.uid = uid
        self._flattened_cache = None
        self._raw: Optional[bytes] = None

    @classmethod
    def all(cls, uid: bool = False) -> 'SequenceSet':
        """A sequence set intended to contain all values."""
        return SequenceSet([(1, '*')], uid)

    @property
    def value(self) -> Sequence[_SeqElem]:
        """The sequence set data."""
        return self.sequences

    @property
    def _flattened(self):
        if self._flattened_cache is None:
            results = []
            for group in self.value:
                if isinstance(group, tuple):
                    group_left, group_right = group
                    if group_left == '*':
                        group_left = math.inf
                    if group_right == '*':
                        group_right = math.inf
                    high = max(group_left, group_right)
                    low = min(group_left, group_right)
                    heapq.heappush(results, (low, high))
                elif group == '*':
                    heapq.heappush(results, (math.inf, math.inf))
                else:
                    heapq.heappush(results, (group, group))
            flattened = []
            while results:
                lowest_min, lowest_max = heapq.heappop(results)
                while results:
                    next_lowest_min, next_lowest_max = results[0]
                    if lowest_max + 1 >= next_lowest_min:
                        heapq.heappop(results)
                        lowest_max = next_lowest_max
                    else:
                        break
                flattened.append((lowest_min, lowest_max))
            self._flattened_cache = flattened
        return self._flattened_cache

    def _get_flattened_bounded(self, max_value: int):
        for low, high in self._flattened:
            low = max_value if math.isinf(low) else low
            high = max_value if math.isinf(high) else high
            if low > max_value:
                break
            elif high > max_value:
                yield (low, max_value)
                break
            else:
                yield (low, high)

    def contains(self, num: int, max_value: int) -> bool:
        """Check if the sequence set contains the given value, when bounded
        by the given maximum value (in place of any ``'*'``).

        Args:
            num: The number to check.
            max_value: The maximum value of the set.

        """
        for low, high in self._get_flattened_bounded(max_value):
            if num < low:
                break
            elif num <= high:
                return True
        return False

    def iter(self, max_value: int) -> Iterable:
        """Iterates through the sequence numbers contained in the set, bounded
        by the given maximum value (in place of any ``'*'``).

        Args:
            max_value: The maximum value of the set.

        """
        return chain.from_iterable(
            [range(min(low, max_value), min(high, max_value) + 1)
             for low, high in self._get_flattened_bounded(max_value)])

    def __bytes__(self) -> bytes:
        if self._raw is not None:
            return self._raw
        parts = []
        for group in self.value:
            if isinstance(group, tuple):
                left = bytes(str(group[0]), 'ascii')
                right = bytes(str(group[1]), 'ascii')
                parts.append(b'%b:%b' % (left, right))
            else:
                parts.append(bytes(str(group), 'ascii'))
        self._raw = raw = b','.join(parts)
        return raw

    def __eq__(self, other) -> bool:
        if isinstance(other, SequenceSet):
            return self.uid == other.uid \
                and self._flattened == other._flattened
        return super().__eq__(other)

    def __hash__(self) -> int:
        return hash((tuple(self.sequences), self.uid))

    @classmethod
    def _parse_part(cls, buf: bytes) -> Tuple[_SeqElem, bytes]:
        if buf and buf[0] == 0x2a:
            item1: _SeqIdx = '*'
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
                return (item1, '*'), buf[1:]
            match = cls._num_pattern.match(buf)
            if match:
                buf = buf[match.end(0):]
                return (item1, int(match.group(0))), buf
            raise NotParseable(buf)
        return item1, buf

    @classmethod
    def build(cls, seqs: Iterable[int], uid: bool = False) -> 'SequenceSet':
        """Build a new sequence set that contains the given values using as
        few groups as possible.

        Args:
            seqs: The sequence values to build.
            uid: True if the sequences refer to message UIDs.

        """
        seqs_list = sorted(set(seqs))
        groups: List[Union[int, Tuple[int, int]]] = []
        group: Union[int, Tuple[int, int]] = seqs_list[0]
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
    def parse(cls, buf: bytes, params: Params) -> Tuple['SequenceSet', bytes]:
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
