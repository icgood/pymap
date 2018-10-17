from itertools import chain
from typing import Iterable, List, Mapping

from . import Response
from ..primitives import ListP, QuotedString, Number
from ..specials import Mailbox, FetchAttribute, StatusAttribute, Flag
from ..typing import MaybeBytes
from ..util import BytesFormat

__all__ = ['FlagsResponse', 'ExistsResponse', 'RecentResponse',
           'ExpungeResponse', 'FetchResponse', 'SearchResponse',
           'StatusResponse', 'ListResponse', 'LSubResponse']


class FlagsResponse(Response):
    """Constructs the special FLAGS response used by the SELECT and EXAMINE
    commands.

    Args:
        flags: Flags in the response.

    """

    def __init__(self, flags: Iterable[MaybeBytes]) -> None:
        text = BytesFormat(b'FLAGS %b') % ListP(flags, sort=True)
        super().__init__(b'*', text)


class ExistsResponse(Response):
    """Constructs the special EXISTS response used by the SELECT and EXAMINE
    commands.

    Args:
        num: The number of messages existing in the mailbox.

    """

    def __init__(self, num: int) -> None:
        text = b'%i EXISTS' % num
        super().__init__(b'*', text)


class RecentResponse(Response):
    """Constructs the special RECENT response used by the SELECT and EXAMINE
    commands.

    Args:
        num: The number of recent messages in the mailbox.

    """

    def __init__(self, num: int) -> None:
        text = b'%i RECENT' % num
        super().__init__(b'*', text)


class ExpungeResponse(Response):
    """Constructs the special EXPUNGE response used by the EXPUNGE command.

    Args:
        seq: The message sequence number.

    """

    def __init__(self, seq: int) -> None:
        text = b'%i EXPUNGE' % seq
        super().__init__(b'*', text)


class FetchResponse(Response):
    """Constructs the special FETCH response used by the STORE and FETCH
    commands.

    Args:
        seq: The message sequence number.
        data: Dictionary mapping fetch attributes to their values.

    """

    def __init__(self, seq: int, data: Mapping[FetchAttribute, MaybeBytes]) \
            -> None:
        items: Iterable[Iterable] = data.items()
        data_list = ListP(chain.from_iterable(items))
        text = BytesFormat(b'%b FETCH %b') % (b'%i' % seq, data_list)
        super().__init__(b'*', text)


class SearchResponse(Response):
    """Constructs the special SEARCH response used by the SEARCH command.

    Args:
        seqs: List of message sequence integers.

    """

    def __init__(self, seqs: Iterable[int]) -> None:
        if seqs:
            text = BytesFormat(b' ').join(
                [b'SEARCH'] + [b'%i' % seq for seq in seqs])
        else:
            text = b'SEARCH'
        super().__init__(b'*', text)


class StatusResponse(Response):
    """Constructs the special STATUS response used by the STATUS command.

    Args:
        name: The name of the mailbox.
        data: Dictionary mapping status attributes to their values.

    """

    def __init__(self, name: str,
                 data: Mapping[StatusAttribute, Number]) -> None:
        items: Iterable[Iterable] = data.items()
        data_list = ListP(chain.from_iterable(items))
        text = b' '.join((b'STATUS', bytes(Mailbox(name)), bytes(data_list)))
        super().__init__(b'*', text)


class ListResponse(Response):
    """Constructs the special LIST response used by the LIST command.

    Args:
        name: The mailbox name.
        sep: The heirarchy separation character.
        marked: If this mailbox is considered "interesting" by the server.
        unmarked: If this mailbox is not considered "interesting".
        no_inferior: If the mailbox does not and cannot have inferior
                        mailboxes in its heirarchy.
        no_select: If the mailbox is not able to be selected.

    """

    name: bytes = b'LIST'

    def __init__(self, name: str, sep: bytes,
                 marked: bool = False,
                 unmarked: bool = False,
                 no_inferior: bool = False,
                 no_select: bool = False) -> None:
        name_attrs: List[Flag] = []
        if marked:
            name_attrs.append(Flag(br'\Marked'))
        elif unmarked:
            name_attrs.append(Flag(br'\Unmarked'))
        if no_inferior:
            name_attrs.append(Flag(br'\Noinferior'))
        if no_select:
            name_attrs.append(Flag(br'\Noselect'))
        text = b' '.join((bytes(self.name),
                          bytes(ListP(name_attrs)),
                          bytes(QuotedString(sep)),
                          bytes(Mailbox(name))))
        super().__init__(b'*', text)


class LSubResponse(ListResponse):
    """Constructs the special LSUB response used by the LSUB command."""

    name = b'LSUB'
