# Copyright (c) 2014 Ian C. Good
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#

import heapq
import re

import math
from itertools import chain
from typing import Iterable, Tuple, List

from . import Special
from .. import NotParseable, Space, Buffer

__all__ = ['SequenceSet']


class SequenceSet(Special):
    """Represents a sequence set from an IMAP stream."""

    _num_pattern = re.compile(br'\d+')

    def __init__(self, sequences, uid=False):
        super().__init__()
        self.sequences = sequences  # type: List
        self.uid = uid  # type: bool
        self._flattened_cache = None
        self._raw = None

    @property
    def _flattened(self):
        if self._flattened_cache is None:
            results = []
            for group in self.sequences:
                if isinstance(group, tuple):
                    if group[0] == '*':
                        group = math.inf, group[1]
                    if group[1] == '*':
                        group = group[0], math.inf
                    high = max(*group)
                    low = min(*group)
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

        :param max_value: The maximum value of the set.

        """
        return chain.from_iterable(
            [range(min(low, max_value), min(high, max_value) + 1)
             for low, high in self._get_flattened_bounded(max_value)])

    def __bytes__(self):
        if self._raw is not None:
            return self._raw
        parts = []
        for group in self.sequences:
            if isinstance(group, tuple):
                left = bytes(str(group[0]), 'ascii')
                right = bytes(str(group[1]), 'ascii')
                parts.append(b'%b:%b' % (left, right))
            else:
                parts.append(bytes(str(group), 'ascii'))
        self._raw = raw = b','.join(parts)
        return raw

    @classmethod
    def _parse_part(cls, buf):
        item1 = None
        if buf and buf[0] == 0x2a:
            item1 = '*'
            buf = buf[1:]
        else:
            match = cls._num_pattern.match(buf)
            if match:
                buf = buf[match.end(0):]
                item1 = int(match.group(0))
        if item1 is None:
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
    def parse(cls, buf: Buffer, uid: bool = False, **_) \
            -> Tuple['SequenceSet', bytes]:
        try:
            _, buf = Space.parse(buf)
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
        return cls(sequences, uid=uid), buf
