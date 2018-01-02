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

"""Defines convenience classes for working with IMAP flags.

.. seealso::

   `RFC 3501 2.3.2 <https://tools.ietf.org/html/rfc3501#section-2.3.2>`_

"""

__all__ = ['CustomFlag', 'Seen', 'Recent', 'Deleted', 'Flagged', 'Answered',
           'Draft']


class Flag(bytes):

    def __new__(cls, value):
        if not value:
            raise ValueError(value)
        return bytes.__new__(cls, cls._capitalize(value))

    @classmethod
    def _capitalize(cls, value):
        if value.startswith(b'\\'):
            return b'\\' + value[1:].capitalize()
        return value

    def __eq__(self, other):
        if isinstance(other, Flag):
            return bytes(self) == bytes(other)
        elif isinstance(other, bytes):
            return bytes(self) == self._capitalize(other)
        return NotImplemented

    def __ne__(self, other):
        return not (self == other)

    def __hash__(self):
        return hash(bytes(self))

    def __repr__(self):
        return '<{0} value={1!r}>'.format(self.__class__.__name__, bytes(self))


class CustomFlag(Flag):
    """Base class for defining custom flag objects. All custom flags, whether
    they are instances or sub-classes, should use this class.

    :param bytes value: The bytestring of the flag's value.

    """
    pass


Seen = Flag(br'\Seen')
Recent = Flag(br'\Recent')
Deleted = Flag(br'\Deleted')
Flagged = Flag(br'\Flagged')
Answered = Flag(br'\Answered')
Draft = Flag(br'\Draft')
