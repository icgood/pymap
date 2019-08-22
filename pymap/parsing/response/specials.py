
from collections import OrderedDict
from itertools import chain
from typing import ClassVar, Tuple, Iterable, Sequence, List, Mapping, Optional

from . import Response
from ..modutf7 import modutf7_encode
from ..primitives import Nil, ListP, QuotedString
from ..specials import Mailbox, FetchAttribute, StatusAttribute
from ...bytes import MaybeBytes, BytesFormat, WriteStream

__all__ = ['FlagsResponse', 'ExistsResponse', 'RecentResponse',
           'ExpungeResponse', 'FetchResponse', 'SearchResponse',
           'ESearchResponse', 'StatusResponse', 'ListResponse',
           'LSubResponse']

_FetchData = Sequence[Tuple[FetchAttribute, MaybeBytes]]


class FlagsResponse(Response):
    """Constructs the special FLAGS response used by the SELECT and EXAMINE
    commands.

    Args:
        flags: Flags in the response.

    """

    def __init__(self, flags: Iterable[MaybeBytes]) -> None:
        super().__init__(b'*')
        self.flags = flags

    @property
    def text(self) -> bytes:
        text = BytesFormat(b'FLAGS %b') % ListP(self.flags, sort=True)
        return super().text + text


class ExistsResponse(Response):
    """Constructs the special EXISTS response used by the SELECT and EXAMINE
    commands.

    Args:
        num: The number of messages existing in the mailbox.

    """

    def __init__(self, num: int) -> None:
        super().__init__(b'*')
        self.num = num

    @property
    def text(self) -> bytes:
        return super().text + b'%i EXISTS' % self.num


class RecentResponse(Response):
    """Constructs the special RECENT response used by the SELECT and EXAMINE
    commands.

    Args:
        num: The number of recent messages in the mailbox.

    """

    def __init__(self, num: int) -> None:
        super().__init__(b'*')
        self.num = num

    @property
    def text(self) -> bytes:
        return super().text + b'%i RECENT' % self.num


class ExpungeResponse(Response):
    """Constructs the special EXPUNGE response used by the EXPUNGE command.

    Args:
        seq: The message sequence number.

    """

    def __init__(self, seq: int) -> None:
        super().__init__(b'*')
        self.seq = seq

    @property
    def text(self) -> bytes:
        return super().text + b'%i EXPUNGE' % self.seq


class FetchResponse(Response):
    """Constructs the special FETCH response used by the STORE and FETCH
    commands.

    Args:
        seq: The message sequence number.
        data: Dictionary mapping fetch attributes to their values.

    """

    def __init__(self, seq: int, data: _FetchData) -> None:
        super().__init__(b'*')
        self.seq = seq
        self.data = list(data)

    @property
    def merge_key(self) -> int:
        return self.seq

    def merge(self: 'FetchResponse', other: 'FetchResponse') \
            -> 'FetchResponse':
        """Merge the other FETCH response, adding any fetch attributes that do
        not already exist in this FETCH response. For example::

            * 3 FETCH (UID 119)
            * 3 FETCH (FLAGS (\\Seen))

        Would merge into::

            * 3 FETCH (UID 119 FLAGS (\\Seen))

        Args:
            other: The other response to merge.

        """
        if self.seq != other.seq:
            raise ValueError(other)
        new_data = OrderedDict(self.data)
        new_data.update(other.data)
        return FetchResponse(self.seq, list(new_data.items()))

    @property
    def text(self) -> bytes:
        data_list = ListP(chain.from_iterable(self.data))
        return BytesFormat(b'%i FETCH %b') % (self.seq, data_list)

    def write(self, writer: WriteStream) -> None:
        writer.write(b'%b %i FETCH ' % (self.tag, self.seq))
        data_list = ListP(chain.from_iterable(self.data))
        data_list.write(writer)
        writer.write(b'\r\n')


class SearchResponse(Response):
    """Constructs the special SEARCH response used by the SEARCH command.

    Args:
        seqs: List of message sequence integers.

    """

    def __init__(self, seqs: Iterable[int]) -> None:
        super().__init__(b'*')
        self.seqs = seqs

    @property
    def text(self) -> bytes:
        text = BytesFormat(b' ').join(
            [b'SEARCH'], [b'%i' % seq for seq in self.seqs])
        return super().text + text


class ESearchResponse(Response):
    """Constructs the special ESEARCH response used by extended SEARCH
    commands. This response should be mutually exclusive with SEARCH responses.

    See Also:
        `RFC 4466 2.6.2. <https://tools.ietf.org/html/rfc4466#section-2.6.2>`_

    Args:
        issuer_tag: The command tag, if issued in response to a command.
        uid: True if the response refers to message UIDs.
        data: The returned search data pairs.

    """

    def __init__(self, issuer_tag: Optional[bytes], uid: bool,
                 data: Mapping[bytes, MaybeBytes]) -> None:
        super().__init__(b'*')
        self.issuer_tag = issuer_tag
        self.uid = uid
        self.data = data

    @property
    def text(self) -> bytes:
        prefixes: List[bytes] = []
        if self.issuer_tag is not None:
            prefixes += [BytesFormat(b'(TAG "%b")') % self.issuer_tag]
        if self.uid:
            prefixes += [b'UID']
        parts = [(item.upper(), bytes(value))
                 for item, value in sorted(self.data.items())]
        return super().text + BytesFormat(b' ').join(prefixes, *parts)


class StatusResponse(Response):
    """Constructs the special STATUS response used by the STATUS command.

    Args:
        name: The name of the mailbox.
        data: Dictionary mapping status attributes to their values.

    """

    def __init__(self, name: str,
                 data: Mapping[StatusAttribute, MaybeBytes]) -> None:
        super().__init__(b'*')
        self.name = name
        self.data = data

    @property
    def text(self) -> bytes:
        data_list = ListP(chain.from_iterable(self.data.items()))
        return super().text + BytesFormat(b' ').join(
            [b'STATUS', Mailbox(self.name), data_list])


class ListResponse(Response):
    """Constructs the special LIST response used by the LIST command.

    Args:
        mailbox: The mailbox name.
        sep: The heirarchy separation character.
        attrs: The attribute flags associated with the mailbox.

    """

    _name: ClassVar[bytes] = b'LIST'

    def __init__(self, mailbox: str, sep: Optional[str],
                 attrs: Iterable[bytes]) -> None:
        super().__init__(b'*')
        self.mailbox = mailbox
        self.sep = sep
        self.attrs = attrs

    @property
    def text(self) -> bytes:
        if self.sep:
            sep_obj: MaybeBytes = QuotedString(modutf7_encode(self.sep))
        else:
            sep_obj = Nil()
        attrs_obj = ListP([b'\\' + attr for attr in self.attrs])
        return super().text + BytesFormat(b' ').join(
            (self._name, attrs_obj, sep_obj, Mailbox(self.mailbox)))


class LSubResponse(ListResponse):
    """Constructs the special LSUB response used by the LSUB command."""

    _name = b'LSUB'
