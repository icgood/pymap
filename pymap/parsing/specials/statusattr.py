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

from .. import NotParseable, Space
from ..primitives import Atom
from . import Special, InvalidContent

__all__ = ['StatusAttribute']


class StatusAttribute(Special):
    """Represents a status attribute from an IMAP stream.

    :param str status: The status attribute name.

    """

    _statuses = set([b'MESSAGES', b'RECENT', b'UIDNEXT', b'UIDVALIDITY',
                     b'UNSEEN'])

    def __init__(self, status):
        super().__init__()
        if status not in self._statuses:
            raise ValueError(status)
        self.value = status

    @classmethod
    def parse(cls, buf, **kwargs):
        try:
            _, buf = Space.parse(buf)
        except NotParseable:
            pass
        atom, after = Atom.parse(buf)
        try:
            return cls(atom.value.upper()), after
        except ValueError:
            raise InvalidContent(buf)

    def __bytes__(self):
        return self.value
