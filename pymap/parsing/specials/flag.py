# Copyright (c) 2018 Ian C. Good
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

from functools import total_ordering
from typing import Tuple

from .. import NotParseable, Space, Params, Special
from ..primitives import Atom

__all__ = ['Flag']


@total_ordering
class Flag(Special[bytes]):
    """Represents a message flag from an IMAP stream."""

    def __init__(self, value: bytes) -> None:
        super().__init__()
        self.value = self._capitalize(value)

    @classmethod
    def _capitalize(cls, value: bytes) -> bytes:
        if value.startswith(b'\\'):
            return b'\\' + value[1:].capitalize()
        return value

    def __eq__(self, other):
        if isinstance(other, Flag):
            return bytes(self) == bytes(other)
        elif isinstance(other, bytes):
            return bytes(self) == self._capitalize(other)
        return NotImplemented

    def __lt__(self, other):
        if isinstance(other, Flag):
            return bytes(self) < bytes(other)
        elif isinstance(other, bytes):
            return bytes(self) < self._capitalize(other)
        return NotImplemented

    def __hash__(self):
        return hash(bytes(self))

    def __repr__(self):
        return '<{0} value={1!r}>'.format(self.__class__.__name__, bytes(self))

    def __bytes__(self):
        return self.value

    @classmethod
    def parse(cls, buf: bytes, params: Params) -> Tuple['Flag', bytes]:
        try:
            _, buf = Space.parse(buf, params)
        except NotParseable:
            pass
        if buf and buf[0] == 0x5c:
            atom, buf = Atom.parse(buf[1:], params)
            return cls(b'\\' + atom.value), buf
        else:
            atom, buf = Atom.parse(buf, params)
            return cls(atom.value), buf
