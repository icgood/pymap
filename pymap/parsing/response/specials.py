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

from itertools import chain

from ..primitives import List, QuotedString
from ..specials import Mailbox

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


class ExistsResponse(Response):
    """Constructs the special EXISTS response used by the SELECT and EXAMINE
    commands.

    :param int num: The number of messages existing in the mailbox.

    """

    def __init__(self, num):
        text = bytes(str(num), 'utf-8') + b' EXISTS'
        super().__init__(b'*', text)


class RecentResponse(Response):
    """Constructs the special RECENT response used by the SELECT and EXAMINE
    commands.

    :param int num: The number of recent messages in the mailbox.

    """

    def __init__(self, num):
        text = bytes(str(num), 'utf-8') + b' RECENT'
        super().__init__(b'*', text)


class ExpungeResponse(Response):
    """Constructs the special EXPUNGE response used by the EXPUNGE command.

    :param int seq: The message sequence number.

    """

    def __init__(self, seq):
        text = bytes(str(seq), 'utf-8') + b' EXPUNGE'
        super().__init__(b'*', text)


class FetchResponse(Response):
    """Constructs the special FETCH response used by the STORE and FETCH
    commands.

    :param int seq: The message sequence number.
    :param dict data: Dictionary where the keys are
                      :class:`~pymap.parsing.specials.FetchAttribute` objects
                      and the values are any object that converted to a
                      bytestring.

    """

    def __init__(self, seq, data):
        seq_raw = bytes(str(seq), 'utf-8')
        data_list = List(chain.from_iterable(data))
        text = b' '.join((seq_raw, b'FETCH', bytes(data_list)))
        super().__init__(b'*', text)


class SearchResponse(Response):
    """Constructs the special SEARCH response used by the SEARCH command.

    :param list seqs: List of message sequence integers.

    """

    def __init__(self, seqs):
        seqs_raw = [bytes(str(seq), 'utf-8') for seq in seqs]
        text = b' '.join([b'SEARCH'] + seqs_raw)
        super().__init__(b'*', text)


class ListResponse(Response):
    """Constructs the special LIST response used by the LIST command.

    :param str name: The mailbox name.
    :param bytes sep: The heirarchy separation character.
    :param bool marked: If this mailbox is considered "interesting" by the
                        server.
    :param bool no_inferior: If the mailbox does not and cannot have inferior
                             mailboxes in its heirarchy.
    :param bool no_select: If the mailbox is not able to be selected.

    """

    name = b'LIST'

    def __init__(self, name, sep, marked=False, no_inferior=False,
                 no_select=False):
        name_attrs = List([])
        if marked:
            name_attrs.append(br'\Marked')
        else:
            name_attrs.append(br'\Unmarked')
        if no_inferior:
            name_attrs.append(br'\Noinferior')
        if no_select:
            name_attrs.append(br'\Noselect')
        sep_raw = bytes(QuotedString(sep))
        name_raw = bytes(Mailbox(name))
        text = b' '.join((self.name, bytes(name_attrs), sep_raw, name_raw))
        super().__init__(b'*', text)


class LSubResponse(Response):
    """Constructs the special LSUB response used by the LSUB command."""

    name = b'LSUB'
