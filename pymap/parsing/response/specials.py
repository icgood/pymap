
from itertools import chain
from typing import Iterable, Mapping, Optional

from . import Response
from ..primitives import Nil, ListP, QuotedString, Number
from ..specials import Mailbox, FetchAttribute, StatusAttribute
from ...bytes import MaybeBytes, BytesFormat

__all__ = ['FlagsResponse', 'ExistsResponse', 'RecentResponse',
           'ExpungeResponse', 'FetchResponse', 'SearchResponse',
           'ESearchResponse', 'StatusResponse', 'ListResponse',
           'LSubResponse']


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


class ESearchResponse(Response):
    """Constructs the special ESEARCH response used by extended SEARCH
    commands. This response should be mutually exclusive with SEARCH responses.

    See Also:
        `RFC 4466 2.6.2. <https://tools.ietf.org/html/rfc4466#section-2.6.2>`_

    Args:
        tag: The command tag, if issued in response to a command.
        uid: True if the response refers to message UIDs.
        data: The returned search data pairs.

    """

    def __init__(self, tag: Optional[bytes], uid: bool,
                 data: Mapping[bytes, MaybeBytes]) -> None:
        if tag is not None:
            tag_prefix = BytesFormat(b'(TAG "%b") ') % tag
        else:
            tag_prefix = b''
        uid_prefix = b'UID ' if uid else b''
        parts = [(item.upper(), bytes(value))
                 for item, value in sorted(data.items())]
        text = BytesFormat(b' ').join(*parts)
        super().__init__(b'*', tag_prefix + uid_prefix + text)


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
        attrs: The attribute flags associated with the mailbox.

    """

    name: bytes = b'LIST'

    def __init__(self, name: str, sep: Optional[str],
                 attrs: Iterable[bytes]) -> None:
        if sep:
            sep_obj: MaybeBytes = QuotedString(sep.encode('utf-8'))
        else:
            sep_obj = Nil()
        attrs_obj = ListP([b'\\' + attr for attr in attrs])
        text = BytesFormat(b' ').join(
            (self.name, attrs_obj, sep_obj, Mailbox(name)))
        super().__init__(b'*', text)


class LSubResponse(ListResponse):
    """Constructs the special LSUB response used by the LSUB command."""

    name = b'LSUB'
