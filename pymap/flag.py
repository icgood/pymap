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

import enum

from .parsing.specials.flag import Flag

__all__ = ['FlagOp', 'CustomFlag', 'Seen', 'Recent', 'Deleted', 'Flagged',
           'Answered', 'Draft']


class FlagOp(enum.Enum):
    """Types of operations when updating flags."""

    #: All existing flags should be replaced with the flag set.
    REPLACE = enum.auto()

    #: The flag set should be added to the existing set.
    ADD = enum.auto()

    #: The flag set should be removed from the existing set.
    DELETE = enum.auto()


class CustomFlag(Flag):
    """Base class for defining custom flag objects. All custom flags, whether
    they are instances or sub-classes, should use this class.

    :param value: The bytes of the flag's value.

    """

    def __init__(self, value: bytes):
        super().__init__(value)


Seen = Flag(br'\Seen')
Recent = Flag(br'\Recent')
Deleted = Flag(br'\Deleted')
Flagged = Flag(br'\Flagged')
Answered = Flag(br'\Answered')
Draft = Flag(br'\Draft')
