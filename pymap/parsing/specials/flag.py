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

from pymap.flags import Flag as FlagClass
from .. import NotParseable, Space
from ..primitives import Atom
from . import Special

__all__ = ['Flag']


class Flag(Special):
    """Represents a message flag from an IMAP stream.

    :param str flag: The flag or keyword string. For system flags, this will
                     start with a backslash (``\``).

    """

    def __init__(self, flag):
        super().__init__()
        self.value = FlagClass(flag)

    @classmethod
    def parse(cls, buf, **kwargs):
        try:
            _, buf = Space.parse(buf)
        except NotParseable:
            pass
        if buf and buf[0] == 0x5c:
            atom, buf = Atom.parse(buf[1:])
            return cls(b'\\' + atom.value), buf
        else:
            atom, buf = Atom.parse(buf)
            return cls(atom.value), buf

    def __bytes__(self):
        return self.value
