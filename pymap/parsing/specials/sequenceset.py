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

import re

from . import Special
from .. import NotParseable, Space

__all__ = ['SequenceSet']


class SequenceSet(Special):
    """Represents a sequence set from an IMAP stream.

    :param list sequences: List of items where each item is either a number, an
                           asterisk (``*``), or a two-item tuple where each
                           part is either a number or an asterisk. E.g.
                           ``[13, '*', ('*', 26), (50, '*')]``.

    """

    _num_pattern = re.compile(br'\d+')

    def __init__(self, sequences):
        super().__init__()
        self.sequences = sequences
        self._raw = None

    def contains(self, num, max_value):
        if num > max_value:
            return False
        for group in self.sequences:
            if group == '*' and num <= max_value:
                return True
            elif isinstance(group, tuple):
                if group[0] == '*':
                    group = max_value, group[1]
                if group[1] == '*':
                    group = group[0], max_value
                high = max(*group)
                low = min(*group)
                if num >= low and num <= high:
                    return True
            elif num == group:
                return True
        return False

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
    def parse(cls, buf, **kwargs):
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
        return cls(sequences), buf

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
