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

from ..primitives import List

from . import Response

__all__ = ['FlagsResponse', 'ExistsResponse', 'RecentResponse']


class FlagsResponse(Response):
    """Constructs the special FLAGS response used by the SELECT and EXAMINE
    commands.

    :param list flags: List of bytestrings or
                       :class:`~pymap.parsing.specials.Flag` objects.

    """

    def __init__(self, flags):
        text = b'FLAGS ' + bytes(List(flags))
        super().__init__(b'*', text)
        self.flags = flags


class ExistsResponse(Response):
    """Constructs the special EXISTS response used by the SELECT and EXAMINE
    commands.

    :param int num: The number of messages existing in the mailbox.

    """

    def __init__(self, num):
        text = bytes(num) + b' EXISTS'
        super().__init__(b'*', text)
        self.num = num


class RecentResponse(Response):
    """Constructs the special RECENT response used by the SELECT and EXAMINE
    commands.

    :param int num: The number of recent messages in the mailbox.

    """

    def __init__(self, num):
        text = bytes(num) + b' RECENT'
        super().__init__(b'*', text)
        self.num = num
