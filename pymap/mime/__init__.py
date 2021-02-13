
from __future__ import annotations

import base64
from collections.abc import Iterable, Mapping, Sequence
from email.headerregistry import ContentTypeHeader
from email.policy import SMTP
from itertools import chain, islice
from typing import Any, Optional, Final

from .parsed import ParsedHeaders
from ._util import whitespace, find_any, get_raw
from ..bytes import WriteStream, Writeable

__all__ = ['MessageContent', 'MessageHeader', 'MessageBody']

_default_type: Final = 'text/plain'

_Line = tuple[int, int, int]
_Lines = Sequence[_Line]
_Folded = Sequence[tuple[str, _Lines]]


class MessageContent(Writeable):
    """Contains the message content, parsed for IMAP processing.

    Args:
        data: The message literal.
        header: The parsed message header.
        body: The parsed message body.

    Attributes:
        lines: The number of lines in the message content.

    """

    __slots__ = ['_raw', 'lines', 'header', 'body', '__weakref__']

    def __init__(self, data: bytes, header: MessageHeader,
                 body: MessageBody) -> None:
        super().__init__()
        self._raw = get_raw(memoryview(data), header._lines, body._lines)
        self.lines: Final = header.lines + body.lines - 1
        self.header: Final = header
        self.body: Final = body

    def walk(self) -> Iterable[MessageContent]:
        """Iterate through the message and all its nested sub-parts in the
        order they occur.

        """
        if self.body.has_nested:
            return chain([self], *(part.walk() for part in self.body.nested))
        else:
            return [self]

    @property
    def is_rfc822(self) -> bool:
        """True if the content-type of the message is ``message/rfc822``."""
        ct_hdr = self.header.parsed.content_type
        if ct_hdr is None:
            return False
        else:
            return ct_hdr.content_type == 'message/rfc822'

    @property
    def json(self) -> Mapping[str, Any]:
        """A dictionary that can be serialized (e.g. with :mod:`json`), so that
        this object may be re-created without parsing.

        See Also:
            :meth:`.from_json`

        """
        return {'header': self.header.json,
                'body': self.body.json}

    @classmethod
    def from_json(cls, data: bytes, json: Mapping[str, Any]) -> MessageContent:
        """Recover the parsed message content without re-parsing, using the
        original raw data and the :attr:`.json`.

        In this example, ``content1`` and ``content2`` should be equivalent::

            message = b'...'
            content1 = MessageContent.parse(message)
            content2 = MessageContent.from_json(message, content1.json)

        Args:
            data: The bytestring that was parsed.
            json: The :attr:`.json` of a previously parsed message content.

        """
        header = MessageHeader.from_json(data, json['header'])
        body = MessageBody.from_json(data, json['body'])
        return cls(data, header, body)

    @classmethod
    def parse(cls, data: bytes) -> MessageContent:
        """Parse the bytestring into message content.

        Args:
            data: The bytestring to parse.

        """
        lines = cls._find_lines(data)
        view = memoryview(data)
        return cls._parse(data, view, lines)

    @classmethod
    def _parse(cls, data: bytes, view: memoryview, lines: _Lines) \
            -> MessageContent:
        header_lines, body_lines = cls._split_lines(data, lines)
        header = MessageHeader._parse(data, view, header_lines)
        content_type = header.parsed.content_type
        body = MessageBody._parse(data, view, body_lines, content_type)
        return cls(data, header, body)

    @classmethod
    def _find_lines(cls, data: bytes) -> _Lines:
        start = 0
        end = len(data)
        ret: list[_Line] = []
        while True:
            idx = data.find(b'\n', start, end)
            if idx < 0:
                ret.append((start, end, end))
                break
            next_start = idx + 1
            idx_minus_1 = idx - 1
            if idx_minus_1 >= start and data[idx_minus_1] == 0x0d:
                idx = idx_minus_1
            ret.append((start, idx, next_start))
            start = next_start
        return ret

    @classmethod
    def _split_lines(cls, data: bytes, lines: _Lines) -> tuple[_Lines, _Lines]:
        for i, line in enumerate(lines):
            start, end, _ = line
            ws_end = find_any(data, whitespace, start, end, False, False)
            if ws_end < 0:
                return lines[0:i + 1], lines[i + 1:]
        return [], lines

    def write(self, writer: WriteStream) -> None:
        writer.write(bytes(self))

    def __len__(self) -> int:
        return len(self._raw)

    def __bytes__(self) -> bytes:
        return bytes(self._raw)


class MessageHeader(Writeable):
    """The message header. Contains lines in the form of ``Header: value\\n``,
    possibly folded onto multiple lines where subsequent lines start with
    whitespace.

    Attributes:
        folded: A list of headers, as they occurred in the original data, as
            tuples of the lower-cased header name and the full header value,
            including the header name and any extra folded lines.
        parsed: The message headers, as a dictionary-like object that parses
            headers on-demand.

    """

    __slots__ = ['_raw', '_lines', '_folded', 'folded', 'parsed']

    def __init__(self, data: bytes, lines: _Lines, folded: _Folded) -> None:
        super().__init__()
        view = memoryview(data)
        self._raw = get_raw(view, lines)
        self._lines = lines
        self._folded = folded
        self.folded: Final = self._get_folded(view, folded)
        self.parsed: Final = self._get_parsed(data, folded)

    @property
    def lines(self) -> int:
        """The number of lines in the message header."""
        return len(self._lines)

    @property
    def json(self) -> Mapping[str, Any]:
        """A dictionary that can be serialized (e.g. with :mod:`json`), so that
        this object may be re-created without parsing.

        See Also:
            :meth:`.from_json`

        """
        return {'lines': self._lines,
                'folded': self._folded}

    @classmethod
    def from_json(cls, data: bytes, json: Mapping[str, Any]) -> MessageHeader:
        """Recover the parsed message header without re-parsing, using the
        original raw data and the :attr:`.json`.

        See Also:
            :meth:`MessageContent.from_json`

        Args:
            data: The bytestring that was parsed.
            json: The :attr:`.json` of a previously parsed message content.

        """
        lines: _Lines = json['lines']
        folded: _Folded = json['folded']
        return cls(data, lines, folded)

    @classmethod
    def empty(cls) -> MessageHeader:
        """Return an empty header object."""
        return cls(b'', [], [])

    @classmethod
    def _get_folded(cls, view: memoryview, folded: _Folded) \
            -> Sequence[tuple[bytes, memoryview]]:
        return [(cls._to_bytes(key), get_raw(view, lines))
                for key, lines in folded]

    @classmethod
    def _get_parsed(cls, data: bytes, folded: _Folded) -> ParsedHeaders:
        header_map: dict[bytes, list[list[bytes]]] = {}
        for key, lines in folded:
            name = cls._to_bytes(key)
            values = header_map.setdefault(name, [])
            values.append([data[start:end] for start, end, _ in lines])
        return ParsedHeaders(header_map)

    @classmethod
    def _to_bytes(cls, key: str) -> bytes:
        return base64.b64decode(key)

    @classmethod
    def _to_str(cls, key: bytes) -> str:
        return base64.b64encode(key).decode('ascii')

    @classmethod
    def _parse(cls, data: bytes, view: memoryview,
               lines: _Lines) -> MessageHeader:
        folds = cls._find_folds(data, lines)
        folded = cls._find_folded(data, view, folds)
        return cls(data, lines, folded)

    @classmethod
    def _find_folds(cls, data: bytes, lines: _Lines) -> Sequence[_Lines]:
        ret: list[list[tuple[int, int, int]]] = []
        if not lines:
            return []
        for line in islice(lines, len(lines) - 1):
            start, end, _ = line
            length = end - start
            if length >= 1 and data[start] in whitespace:
                if ret:
                    ret[-1].append(line)
            else:
                ret.append([line])
        return ret

    @classmethod
    def _find_folded(cls, data: bytes, view: memoryview,
                     folds: Sequence[_Lines]) -> _Folded:
        folded: list[tuple[str, _Lines]] = []
        for group in folds:
            start, end, _ = group[0]
            colon = data.find(b':', start, end)
            if colon < 0:
                continue
            name = data[start:colon].strip().lower()
            folded.append((cls._to_str(name), group))
        return folded

    def write(self, writer: WriteStream) -> None:
        writer.write(bytes(self))

    def __len__(self) -> int:
        return len(self._raw)

    def __bytes__(self) -> bytes:
        return bytes(self._raw)


class MessageBody(Writeable):
    """The message body, starting immediately after the header. The body may
    contain nested sub-parts, which are each valid :class:`MessageContent`
    objects.

    Attributes:
        content_type: The content type of the message body.

    """

    __slots__ = ['_raw', '_lines', '_nested', 'content_type']

    def __init__(self, data: bytes, lines: _Lines,
                 content_type: ContentTypeHeader,
                 nested: Sequence[MessageContent]) -> None:
        super().__init__()
        self._raw = get_raw(memoryview(data), lines)
        self._lines = lines
        self._nested = nested
        self.content_type: Final = content_type

    @property
    def lines(self) -> int:
        """The number of lines in the message body."""
        return len(self._lines)

    @property
    def has_nested(self) -> bool:
        """True if the message body is composed of nested sub-parts."""
        return len(self.nested) > 0

    @property
    def nested(self) -> Sequence[MessageContent]:
        """If :attr:`.has_nested` is True, contains the list of sub-parts."""
        return self._nested

    @property
    def json(self) -> Mapping[str, Any]:
        """A dictionary that can be serialized (e.g. with :mod:`json`), so that
        this object may be re-created without parsing.

        See Also:
            :meth:`.from_json`

        """
        return {'lines': self._lines,
                'content_type': str(self.content_type),
                'nested': [part.json for part in self._nested]}

    @classmethod
    def from_json(cls, data: bytes, json: Mapping[str, Any]) -> MessageBody:
        """Recover the parsed message body without re-parsing, using the
        original raw data and the :attr:`.json`.

        See Also:
            :meth:`MessageContent.from_json`

        Args:
            data: The bytestring that was parsed.
            json: The :attr:`.json` of a previously parsed message content.

        """
        lines: _Lines = json['lines']
        content_type = cls._parse_content_type(json['content_type'])
        nested = [MessageContent.from_json(data, part)
                  for part in json['nested']]
        return cls(data, lines, content_type, nested)

    @classmethod
    def empty(cls) -> MessageBody:
        """Return an empty body object."""
        content_type = cls._parse_content_type(_default_type)
        return cls(b'', [], content_type, [])

    @classmethod
    def _parse(cls, data: bytes, view: memoryview, lines: _Lines,
               content_type: Optional[ContentTypeHeader]) -> MessageBody:
        if content_type is None:
            content_type = cls._parse_content_type(_default_type)
        maintype = content_type.maintype
        if maintype == 'multipart':
            boundary = cls._get_boundary(content_type)
            if boundary:
                return cls._parse_multipart(
                    data, view, lines, content_type, boundary)
        elif maintype == 'message' and content_type.subtype == 'rfc822':
            return cls._parse_rfc822(data, view, lines, content_type)
        return cls(data, lines, content_type, [])

    @classmethod
    def _parse_content_type(cls, header: str) -> ContentTypeHeader:
        return SMTP.header_fetch_parse('Content-Type', header)  # type: ignore

    @classmethod
    def _get_boundary(cls, content_type: ContentTypeHeader) -> Optional[bytes]:
        try:
            boundary = content_type.params['boundary']
        except KeyError:
            pass
        else:
            if boundary:
                try:
                    return boundary.encode('ascii')
                except UnicodeError:
                    pass
        return None

    @classmethod
    def _parse_rfc822(cls, data: bytes, view: memoryview, lines: _Lines,
                      content_type: ContentTypeHeader) -> MessageBody:
        subpart = MessageContent._parse(data, view, lines)
        return cls(data, lines, content_type, [subpart])

    @classmethod
    def _parse_multipart(cls, data: bytes, view: memoryview, lines: _Lines,
                         content_type: ContentTypeHeader,
                         boundary: bytes) -> MessageBody:
        parts = cls._find_parts(data, view, lines, boundary)
        nested: list[MessageContent] = []
        for part_lines in parts:
            sub_content = MessageContent._parse(data, view, part_lines)
            nested.append(sub_content)
        return cls(data, lines, content_type, nested)

    @classmethod
    def _find_parts(cls, data: bytes, view: memoryview, lines: _Lines,
                    boundary: bytes) -> Sequence[_Lines]:
        ret: list[list[_Line]] = []
        part_match = (b'--%s' % boundary, b'--%s' % boundary)
        stop_match = (b'--%s--' % boundary, b'--%s--' % boundary)
        for line in lines:
            start, end, _ = line
            line_view = view[start:end]
            if any(line_view == m for m in stop_match):
                break
            elif any(line_view == m for m in part_match):
                ret.append([])
            elif ret:
                ret[-1].append(line)
        return ret

    def write(self, writer: WriteStream) -> None:
        writer.write(bytes(self))

    def __len__(self) -> int:
        return len(self._raw)

    def __bytes__(self) -> bytes:
        return bytes(self._raw)
