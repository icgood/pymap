
from __future__ import annotations

from collections.abc import Iterable, Mapping
from contextlib import AbstractAsyncContextManager
from itertools import chain
from typing import Optional, ClassVar

from . import UntaggedResponse
from ..modutf7 import modutf7_encode
from ..primitives import Nil, List, QuotedString
from ..specials import Mailbox, FetchAttribute, FetchValue, StatusAttribute
from ...bytes import MaybeBytes, BytesFormat, WriteStream

__all__ = ['FlagsResponse', 'ExistsResponse', 'RecentResponse',
           'ExpungeResponse', 'FetchResponse', 'SearchResponse',
           'ESearchResponse', 'StatusResponse', 'ListResponse',
           'LSubResponse']


class FlagsResponse(UntaggedResponse):
    """Constructs the special FLAGS response used by the SELECT and EXAMINE
    commands.

    Args:
        flags: Flags in the response.

    """

    def __init__(self, flags: Iterable[MaybeBytes]) -> None:
        super().__init__()
        self.flags = flags

    @property
    def text(self) -> bytes:
        text = BytesFormat(b'FLAGS %b') % List(self.flags, sort=True)
        return super().text + text


class ExistsResponse(UntaggedResponse):
    """Constructs the special EXISTS response used by the SELECT and EXAMINE
    commands.

    Args:
        num: The number of messages existing in the mailbox.

    """

    def __init__(self, num: int) -> None:
        super().__init__()
        self.num = num

    @property
    def text(self) -> bytes:
        return super().text + b'%i EXISTS' % self.num


class RecentResponse(UntaggedResponse):
    """Constructs the special RECENT response used by the SELECT and EXAMINE
    commands.

    Args:
        num: The number of recent messages in the mailbox.

    """

    def __init__(self, num: int) -> None:
        super().__init__()
        self.num = num

    @property
    def text(self) -> bytes:
        return super().text + b'%i RECENT' % self.num


class ExpungeResponse(UntaggedResponse):
    """Constructs the special EXPUNGE response used by the EXPUNGE command.

    Args:
        seq: The message sequence number.

    """

    def __init__(self, seq: int) -> None:
        super().__init__()
        self.seq = seq

    @property
    def text(self) -> bytes:
        return super().text + b'%i EXPUNGE' % self.seq


class FetchResponse(UntaggedResponse):
    """Constructs the special FETCH response used by the STORE and FETCH
    commands.

    Args:
        seq: The message sequence number.
        data: Fetch attributes and values for the message.
        writing_hook: An async context manager to enter while the untagged
            response is being written.

    """

    def __init__(self, seq: int, data: Iterable[FetchValue], *,
                 writing_hook: AbstractAsyncContextManager[None] = None) \
            -> None:
        super().__init__(writing_hook=writing_hook)
        self.seq = seq
        self.data: dict[FetchAttribute, FetchValue] = {
            attr.attribute: attr for attr in data}

    @property
    def merge_key(self) -> int:
        return self.seq

    def merge(self, other: FetchResponse) -> FetchResponse:
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
        new_data = self.data | other.data
        writing_hook = other.writing_hook or self.writing_hook
        return FetchResponse(self.seq, new_data.values(),
                             writing_hook=writing_hook)

    @property
    def text(self) -> bytes:
        return b'%i FETCH' % (self.seq, )

    def write(self, writer: WriteStream) -> None:
        writer.write(b'%b %b ' % (self.tag, self.text))
        data_list = List(self.data.values())
        data_list.write(writer)
        writer.write(b'\r\n')


class SearchResponse(UntaggedResponse):
    """Constructs the special SEARCH response used by the SEARCH command.

    Args:
        seqs: List of message sequence integers.

    """

    def __init__(self, seqs: Iterable[int]) -> None:
        super().__init__()
        self.seqs = seqs

    @property
    def text(self) -> bytes:
        text = BytesFormat(b' ').join(
            [b'SEARCH'], [b'%i' % seq for seq in self.seqs])
        return super().text + text


class ESearchResponse(UntaggedResponse):
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
        super().__init__()
        self.issuer_tag = issuer_tag
        self.uid = uid
        self.data = data

    @property
    def text(self) -> bytes:
        prefixes: list[bytes] = []
        if self.issuer_tag is not None:
            prefixes += [BytesFormat(b'(TAG "%b")') % self.issuer_tag]
        if self.uid:
            prefixes += [b'UID']
        parts = [(item.upper(), bytes(value))
                 for item, value in sorted(self.data.items())]
        return super().text + BytesFormat(b' ').join(prefixes, *parts)


class StatusResponse(UntaggedResponse):
    """Constructs the special STATUS response used by the STATUS command.

    Args:
        name: The name of the mailbox.
        data: Dictionary mapping status attributes to their values.

    """

    def __init__(self, name: str,
                 data: Mapping[StatusAttribute, MaybeBytes]) -> None:
        super().__init__()
        self.name = name
        self.data = data

    @property
    def text(self) -> bytes:
        data_list = List(chain.from_iterable(self.data.items()))
        return super().text + BytesFormat(b' ').join(
            [b'STATUS', Mailbox(self.name), data_list])


class ListResponse(UntaggedResponse):
    """Constructs the special LIST response used by the LIST command.

    Args:
        mailbox: The mailbox name.
        sep: The heirarchy separation character.
        attrs: The attribute flags associated with the mailbox.

    """

    _name: ClassVar[bytes] = b'LIST'

    def __init__(self, mailbox: str, sep: Optional[str],
                 attrs: Iterable[bytes]) -> None:
        super().__init__()
        self.mailbox = mailbox
        self.sep = sep
        self.attrs = attrs

    @property
    def text(self) -> bytes:
        if self.sep:
            sep_obj: MaybeBytes = QuotedString(modutf7_encode(self.sep))
        else:
            sep_obj = Nil()
        attrs_obj = List([b'\\' + attr for attr in self.attrs])
        return super().text + BytesFormat(b' ').join(
            (self._name, attrs_obj, sep_obj, Mailbox(self.mailbox)))


class LSubResponse(ListResponse):
    """Constructs the special LSUB response used by the LSUB command."""

    _name = b'LSUB'
