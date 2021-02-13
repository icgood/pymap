
from __future__ import annotations

import enum
from abc import ABCMeta
from collections.abc import Iterable, Sequence
from functools import total_ordering, reduce
from typing import Optional, Final

from . import AString
from .. import Params, Parseable
from ..exceptions import NotParseable
from ..primitives import Atom, List
from ...bytes import rev, BytesFormat, MaybeBytes, Writeable

__all__ = ['FetchRequirement', 'FetchAttribute', 'FetchValue']


class FetchRequirement(enum.Flag):
    """Indicates the data required to fulfill a message fetch.

    Attributes:
        NONE: No data is required.
        METADATA: The IMAP metadata is required.
        HEADER: The message header is required.
        BODY: The parsed MIME message body is required.

    """

    NONE = 0
    METADATA = enum.auto()
    HEADER = enum.auto()
    BODY = enum.auto()
    CONTENT = HEADER | BODY

    def has_all(self, expected: FetchRequirement) -> bool:
        """Returns true if all of the expected fetch requirements are met by
        this fetch requirement.

        Args:
            expected: The expected fetch requirements.

        """
        return self & expected == expected

    def has_none(self, expected: FetchRequirement) -> bool:
        """Returns true if none of the expected fetch requirements are met by
        this fetch requirement.

        Args:
            expected: The expected fetch requirements.

        """
        return self & expected == FetchRequirement.NONE

    @classmethod
    def get_all(cls) -> FetchRequirement:
        """Return all possible fetch requirements reduced into a single
        requirement.

        """
        return cls.reduce(FetchRequirement)

    @classmethod
    def reduce(cls, requirements: Iterable[FetchRequirement]) \
            -> FetchRequirement:
        """Reduce a set of fetch requirements into a single requirement.

        Args:
            requirements: The set of fetch requirements.

        """
        return reduce(lambda x, y: x | y, requirements, cls.NONE)


@total_ordering
class FetchAttribute(Parseable[bytes]):
    """Represents an attribute that should be fetched for each message in the
    sequence set of a FETCH command on an IMAP stream.

    Args:
        attribute: The attribute name.
        section: The attribute section.
        partial: The attribute partial range.

    Attributes:
        section: The attribute section.
        partial: The attribute partial range.

    """

    class Section:
        """Represents a fetch attribute section, which typically comes after
        the attribute name within square brackets, e.g. ``BODY[1.TEXT]``.

        Args:
            parts: The nested MIME part identifiers.
            specifier: The MIME part specifier.
            headers: The MIME part specifier headers.

        """

        def __init__(self, parts: Sequence[int],
                     specifier: bytes = None,
                     headers: frozenset[bytes] = None) -> None:
            self.parts = parts
            self.specifier = specifier
            self.headers = frozenset(hdr.upper() for hdr in headers) \
                if headers else None

        def __hash__(self) -> int:
            return hash((tuple(self.parts), self.specifier, self.headers))

    _attrname_pattern = rev.compile(br' *([^\s\[<()]+)')
    _section_start_pattern = rev.compile(br' *\[ *')
    _section_end_pattern = rev.compile(br' *\]')
    _partial_pattern = rev.compile(br'< *(\d+) *\. *(\d+) *>')

    _sec_part_pattern = rev.compile(br'([1-9]\d* *(?:\. *[1-9]\d*)*) *(\.)? *')

    def __init__(self, attribute: bytes,
                 section: FetchAttribute.Section = None,
                 partial: tuple[int, Optional[int]] = None) -> None:
        super().__init__()
        self.attribute = attribute.upper()
        self.section = section
        self.partial = partial
        self._raw: Optional[bytes] = None
        self._for_response: Optional[FetchAttribute] = None

    @property
    def value(self) -> bytes:
        """The attribute name."""
        return self.attribute

    @property
    def for_response(self) -> FetchAttribute:
        if self._for_response is None:
            if self.partial is None or len(self.partial) < 2:
                self._for_response = self
            else:
                self._for_response = FetchAttribute(
                    self.value, self.section, (self.partial[0], None))
        return self._for_response

    @property
    def set_seen(self) -> bool:
        if self.value == b'BODY' and self.section:
            return True
        elif self.value == b'BINARY':
            return True
        elif self.value in (b'RFC822', b'RFC822.TEXT'):
            return True
        return False

    @property
    def requirement(self) -> FetchRequirement:
        """Indicates the data required to fulfill this fetch attribute."""
        attr_name = self.attribute
        if attr_name in (b'UID', b'FLAGS', b'INTERNALDATE'):
            return FetchRequirement.METADATA
        elif attr_name in (b'ENVELOPE', b'RFC822.HEADER'):
            return FetchRequirement.HEADER
        elif attr_name == b'BODY' and self.section is not None:
            return self._get_body_requirement(self.section)
        return FetchRequirement.CONTENT

    @classmethod
    def _get_body_requirement(cls, section: FetchAttribute.Section) \
            -> FetchRequirement:
        if not section.parts and section.specifier in (
                b'HEADER', b'HEADER.FIELDS', b'HEADER.FIELDS.NOT'):
            return FetchRequirement.HEADER
        else:
            return FetchRequirement.CONTENT

    @property
    def raw(self) -> bytes:
        if self._raw is not None:
            return self._raw
        if self.value == b'BODY.PEEK':
            parts = [b'BODY']
        else:
            parts = [self.value]
        if self.section and not self.value.startswith(b'RFC822'):
            parts.append(b'[')
            if self.section.parts:
                part_raw = BytesFormat(b'.').join(
                    [b'%i' % num for num in self.section.parts])
                parts.append(part_raw)
                if self.section.specifier:
                    parts.append(b'.')
            if self.section.specifier:
                parts.append(self.section.specifier)
                if self.section.headers:
                    headers = self.section.headers
                    parts.append(b' ')
                    parts.append(bytes(List(headers, sort=True)))
            parts.append(b']')
        if self.partial:
            partial = BytesFormat(b'.').join(
                [b'%i' % num for num in self.partial if num is not None])
            parts += [b'<', partial, b'>']
        self._raw = raw = b''.join(parts)
        return raw

    def __hash__(self) -> int:
        return hash((self.value, self.section, self.partial))

    def __eq__(self, other) -> bool:
        if isinstance(other, FetchAttribute):
            return hash(self) == hash(other)
        return super().__eq__(other)

    def __ne__(self, other) -> bool:
        if isinstance(other, FetchAttribute):
            return hash(self) != hash(other)
        return super().__ne__(other)

    def __lt__(self, other) -> bool:
        if not isinstance(other, FetchAttribute):
            return NotImplemented
        return bytes(self.for_response) < bytes(self.for_response)

    @classmethod
    def _parse_section(cls, buf: memoryview, params: Params):
        match = cls._sec_part_pattern.match(buf)
        if match:
            section_parts = [int(num) for num in match.group(1).split(b'.')]
            buf = buf[match.end(0):]
        else:
            section_parts = []
        try:
            atom, after = Atom.parse(buf, params)
        except NotParseable:
            return cls.Section(section_parts), buf
        specifier = atom.value.upper()
        if section_parts and specifier == b'MIME':
            return cls.Section(section_parts, specifier), after
        elif specifier in (b'HEADER', b'TEXT'):
            return cls.Section(section_parts, specifier), after
        elif specifier in (b'HEADER.FIELDS', b'HEADER.FIELDS.NOT'):
            params = params.copy(list_expected=[AString])
            header_list_p, buf = List.parse(after, params)
            header_list = frozenset([bytes(hdr)
                                     for hdr in header_list_p.value])
            if not header_list:
                raise NotParseable(after)
            return cls.Section(section_parts, specifier, header_list), buf
        raise NotParseable(buf)

    @classmethod
    def parse(cls, buf: memoryview, params: Params) \
            -> tuple[FetchAttribute, memoryview]:
        match = cls._attrname_pattern.match(buf)
        if not match:
            raise NotParseable(buf)
        attr = match.group(1).upper()
        after = buf[match.end(0):]
        if attr in (b'ENVELOPE', b'FLAGS', b'INTERNALDATE', b'UID',
                    b'RFC822.SIZE',  b'BODYSTRUCTURE', b'EMAILID',
                    b'THREADID'):
            return cls(attr), after
        elif attr == b'RFC822':
            section = cls.Section([])
            return cls(attr, section), after
        elif attr == b'RFC822.HEADER':
            section = cls.Section([], b'HEADER')
            return cls(attr, section), after
        elif attr == b'RFC822.TEXT':
            section = cls.Section([], b'TEXT')
            return cls(attr, section), after
        elif attr not in (b'BODY', b'BODY.PEEK',
                          b'BINARY', b'BINARY.PEEK', b'BINARY.SIZE'):
            raise NotParseable(buf)
        buf = after
        match = cls._section_start_pattern.match(buf)
        if not match:
            if attr == b'BODY':
                return cls(attr), buf
            else:
                raise NotParseable(buf)
        buf = buf[match.end(0):]
        section, buf_s = cls._parse_section(buf, params)
        if section.specifier and attr.startswith(b'BINARY'):
            raise NotParseable(buf)
        match = cls._section_end_pattern.match(buf_s)
        if not match:
            raise NotParseable(buf_s)
        buf = buf_s[match.end(0):]
        match = cls._partial_pattern.match(buf)
        if match:
            if attr == b'BINARY.SIZE':
                raise NotParseable(buf)
            from_, to = int(match.group(1)), int(match.group(2))
            if from_ < 0 or to <= 0 or from_ > to:
                raise NotParseable(buf)
            return cls(attr, section, (from_, to)), buf[match.end(0):]
        return cls(attr, section), buf

    def __bytes__(self) -> bytes:
        return self.raw


class FetchValue(Writeable, metaclass=ABCMeta):
    """A value fetched from a message for a single fetch attribute.

    Args:
        attribute: The fetch attribute.

    """

    __slots__ = ['attribute']

    def __init__(self, attribute: FetchAttribute) -> None:
        super().__init__()
        self.attribute: Final = attribute

    @classmethod
    def of(cls, attribute: FetchAttribute, value: MaybeBytes) \
            -> FetchValue:
        return _StaticFetchValue(attribute, value)


class _StaticFetchValue(FetchValue):

    __slots__ = ['_value']

    def __init__(self, attribute: FetchAttribute, value: MaybeBytes) -> None:
        super().__init__(attribute)
        self._value: Final = value

    def __bytes__(self) -> bytes:
        attr = self.attribute.for_response
        return BytesFormat(b'%b %b') % (attr, self._value)
