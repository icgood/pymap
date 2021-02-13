
from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping, Sequence
from email.headerregistry import HeaderRegistry, BaseHeader, \
    UnstructuredHeader, DateHeader, AddressHeader, SingleAddressHeader, \
    ContentDispositionHeader, ContentTransferEncodingHeader, ContentTypeHeader
from email.policy import SMTP
from typing import cast, Any, Optional, ClassVar

__all__ = ['ParsedHeaders']

_Headers = Mapping[bytes, Sequence[Sequence[bytes]]]


class ParsedHeaders(Mapping[bytes, Sequence[BaseHeader]]):
    """The mapping of message headers, parsed on-demand using a
    :class:`~email.headerregistry.HeaderRegistry`. Also provides typed
    properties for standard headers used in IMAP processing.

    """

    _registry: ClassVar[HeaderRegistry] = HeaderRegistry()

    __slots__ = ['_headers', '_parsed']

    def __init__(self, headers: _Headers) -> None:
        super().__init__()
        self._headers = headers
        self._parsed: dict[bytes, Sequence[BaseHeader]] = {}

    def __getitem__(self, name: bytes) -> Sequence[BaseHeader]:
        name_lower = name.lower()
        parsed = self._parsed.get(name_lower)
        if parsed is not None:
            return parsed
        values = self._headers[name_lower]
        self._parsed[name_lower] = parsed = list(self._parse(values))
        return parsed

    def __len__(self) -> int:
        return len(self._headers)

    def __contains__(self, name: Any) -> bool:
        if not isinstance(name, bytes):
            raise TypeError(name)
        return name.lower() in self._headers

    def __iter__(self) -> Iterator[bytes]:
        return iter(self._headers.keys())

    @classmethod
    def _parse(cls, values: Sequence[Sequence[bytes]]) \
            -> Iterable[BaseHeader]:
        for value in values:
            lines = [line.decode('ascii', 'surrogateescape')
                     for line in value]
            # TODO: Once typeshed merges this fix:
            #   https://github.com/python/typeshed/pull/4365
            # assign to hdr_name, hdr_value = ... instead.
            hdr_tuple = SMTP.header_source_parse(lines)
            yield cls._registry(hdr_tuple[0], hdr_tuple[1])

    def __repr__(self) -> str:
        return repr(dict(self))

    @property
    def content_type(self) -> Optional[ContentTypeHeader]:
        """The ``Content-Type`` header."""
        try:
            return cast(ContentTypeHeader, self[b'content-type'][0])
        except (KeyError, IndexError):
            return None

    @property
    def date(self) -> Optional[DateHeader]:
        """The ``Date`` header."""
        try:
            return cast(DateHeader, self[b'date'][0])
        except (KeyError, IndexError):
            return None

    @property
    def subject(self) -> Optional[UnstructuredHeader]:
        """The ``Subject`` header."""
        try:
            return cast(UnstructuredHeader, self[b'subject'][0])
        except (KeyError, IndexError):
            return None

    @property
    def from_(self) -> Optional[Sequence[AddressHeader]]:
        """The ``From`` header."""
        try:
            return cast(Sequence[AddressHeader], self[b'from'])
        except KeyError:
            return None

    @property
    def sender(self) -> Optional[Sequence[SingleAddressHeader]]:
        """The ``Sender`` header."""
        try:
            return cast(Sequence[SingleAddressHeader], self[b'sender'])
        except KeyError:
            return None

    @property
    def reply_to(self) -> Optional[Sequence[AddressHeader]]:
        """The ``Reply-To`` header."""
        try:
            return cast(Sequence[AddressHeader], self[b'reply-to'])
        except KeyError:
            return None

    @property
    def to(self) -> Optional[Sequence[AddressHeader]]:
        """The ``To`` header."""
        try:
            return cast(Sequence[AddressHeader], self[b'to'])
        except KeyError:
            return None

    @property
    def cc(self) -> Optional[Sequence[AddressHeader]]:
        """The ``Cc`` header."""
        try:
            return cast(Sequence[AddressHeader], self[b'cc'])
        except KeyError:
            return None

    @property
    def bcc(self) -> Optional[Sequence[AddressHeader]]:
        """The ``Bcc`` header."""
        try:
            return cast(Sequence[AddressHeader], self[b'bcc'])
        except KeyError:
            return None

    @property
    def in_reply_to(self) -> Optional[UnstructuredHeader]:
        """The ``In-Reply-To`` header."""
        try:
            return cast(UnstructuredHeader, self[b'in-reply-to'][0])
        except (KeyError, IndexError):
            return None

    @property
    def references(self) -> Optional[UnstructuredHeader]:
        """The ``References`` header."""
        try:
            return cast(UnstructuredHeader, self[b'references'][0])
        except (KeyError, IndexError):
            return None

    @property
    def message_id(self) -> Optional[UnstructuredHeader]:
        """The ``Message-Id`` header."""
        try:
            return cast(UnstructuredHeader, self[b'message-id'][0])
        except (KeyError, IndexError):
            return None

    @property
    def content_disposition(self) -> Optional[ContentDispositionHeader]:
        """The ``Content-Disposition`` header."""
        try:
            return cast(ContentDispositionHeader,
                        self[b'content-disposition'][0])
        except (KeyError, IndexError):
            return None

    @property
    def content_language(self) -> Optional[UnstructuredHeader]:
        """The ``Content-Language`` header."""
        try:
            return cast(UnstructuredHeader, self[b'content-language'][0])
        except (KeyError, IndexError):
            return None

    @property
    def content_location(self) -> Optional[UnstructuredHeader]:
        """The ``Content-Location`` header."""
        try:
            return cast(UnstructuredHeader, self[b'content-location'][0])
        except (KeyError, IndexError):
            return None

    @property
    def content_id(self) -> Optional[UnstructuredHeader]:
        """The ``Content-Id`` header."""
        try:
            return cast(UnstructuredHeader, self[b'content-id'][0])
        except (KeyError, IndexError):
            return None

    @property
    def content_description(self) -> Optional[UnstructuredHeader]:
        """The ``Content-Description`` header."""
        try:
            return cast(UnstructuredHeader, self[b'content-description'][0])
        except (KeyError, IndexError):
            return None

    @property
    def content_transfer_encoding(self) \
            -> Optional[ContentTransferEncodingHeader]:
        """The ``Content-Transfer-Encoding`` header."""
        try:
            return cast(ContentTransferEncodingHeader,
                        self[b'content-transfer-encoding'][0])
        except (KeyError, IndexError):
            return None
