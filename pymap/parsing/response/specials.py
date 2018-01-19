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
from typing import Collection, Dict, SupportsBytes

from pymap.parsing.specials import FetchAttribute, StatusAttribute
from . import Response
from ..primitives import List, QuotedString, Number
from ..specials import Mailbox

__all__ = ['FlagsResponse', 'ExistsResponse', 'RecentResponse',
           'ExpungeResponse', 'FetchResponse', 'SearchResponse',
           'StatusResponse', 'ListResponse', 'LSubResponse']


class FlagsResponse(Response):
    """Constructs the special FLAGS response used by the SELECT and EXAMINE
    commands.

    :param flags: Flags in the response.

    """

    def __init__(self, flags: Collection[bytes]):
        text = b'FLAGS %b' % List(flags)
        super().__init__(b'*', text)


class ExistsResponse(Response):
    """Constructs the special EXISTS response used by the SELECT and EXAMINE
    commands.

    :param num: The number of messages existing in the mailbox.

    """

    def __init__(self, num: int):
        text = b'%i EXISTS' % num
        super().__init__(b'*', text)


class RecentResponse(Response):
    """Constructs the special RECENT response used by the SELECT and EXAMINE
    commands.

    :param num: The number of recent messages in the mailbox.

    """

    def __init__(self, num: int):
        text = b'%i RECENT' % num
        super().__init__(b'*', text)


class ExpungeResponse(Response):
    """Constructs the special EXPUNGE response used by the EXPUNGE command.

    :param seq: The message sequence number.

    """

    def __init__(self, seq: int):
        text = b'%i EXPUNGE' % seq
        super().__init__(b'*', text)


class FetchResponse(Response):
    """Constructs the special FETCH response used by the STORE and FETCH
    commands.

    :param seq: The message sequence number.
    :param data: Dictionary mapping fetch attributes to their values.

    """

    def __init__(self, seq: int, data: Dict[FetchAttribute, SupportsBytes]):
        data_list = List(chain.from_iterable(data.items()))
        text = b'%i FETCH %b' % (seq, bytes(data_list))
        super().__init__(b'*', text)


class SearchResponse(Response):
    """Constructs the special SEARCH response used by the SEARCH command.

    :param seqs: List of message sequence integers.

    """

    def __init__(self, seqs: Collection[int]):
        seqs_raw = [b'%i' % seq for seq in seqs]
        text = b' '.join([b'SEARCH'] + seqs_raw)
        super().__init__(b'*', text)


class StatusResponse(Response):
    """Constructs the special STATUS response used by the STATUS command.

    :param name: The name of the mailbox.
    :param data: Dictionary mapping status attributes to their values.

    """

    def __init__(self, name: str, data: Dict[StatusAttribute, Number]):
        data_list = List(chain.from_iterable(data.items()))
        text = b' '.join((b'STATUS', bytes(Mailbox(name)), bytes(data_list)))
        super().__init__(b'*', text)


class ListResponse(Response):
    """Constructs the special LIST response used by the LIST command.

    :param name: The mailbox name.
    :param sep: The heirarchy separation character.
    :param marked: If this mailbox is considered "interesting" by the server.
    :param no_inferior: If the mailbox does not and cannot have inferior
                        mailboxes in its heirarchy.
    :param no_select: If the mailbox is not able to be selected.

    """

    name = b'LIST'  # type: bytes

    def __init__(self, name: str, sep: bytes,
                 marked: bool = False,
                 no_inferior: bool = False,
                 no_select: bool = False):
        name_attrs = List([])
        if marked:
            name_attrs.value.append(br'\Marked')
        else:
            name_attrs.value.append(br'\Unmarked')
        if no_inferior:
            name_attrs.value.append(br'\Noinferior')
        if no_select:
            name_attrs.value.append(br'\Noselect')
        text = b' '.join((bytes(self.name),
                          bytes(name_attrs),
                          bytes(QuotedString(sep)),
                          bytes(Mailbox(name))))
        super().__init__(b'*', text)


class LSubResponse(ListResponse):
    """Constructs the special LSUB response used by the LSUB command."""

    name = b'LSUB'
