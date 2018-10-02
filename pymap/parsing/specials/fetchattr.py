# Copyright (c) 2018 Ian C. Good
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

import re
from functools import total_ordering
from typing import Tuple, Optional, Sequence, Iterable

from . import AString
from .. import NotParseable, Params, Special
from ..primitives import Atom, ListP

__all__ = ['FetchAttribute']


@total_ordering
class FetchAttribute(Special[bytes]):
    """Represents an attribute that should be fetched for each message in the
    sequence set of a FETCH command on an IMAP stream.

    """

    class Section:

        def __init__(self, parts: Optional[Iterable[int]],
                     msgtext: bytes = None,
                     headers: Iterable[bytes] = None) -> None:
            self.parts = parts
            self.msgtext = msgtext
            self.headers = headers

        def __hash__(self):
            return hash((self.parts, self.msgtext, self.headers))

    _attrname_pattern = re.compile(br' *([^\s\[<()]+)')
    _section_start_pattern = re.compile(br' *\[ *')
    _section_end_pattern = re.compile(br' *\]')
    _partial_pattern = re.compile(br'< *(\d+) *\. *(\d+) *>')

    _sec_part_pattern = re.compile(br'(\d+ *(?:\. *\d+)*) *(\.)? *(MIME)?',
                                   re.I)

    def __init__(self, attribute: bytes,
                 section: Section = None,
                 partial: Sequence[int] = None) -> None:
        super().__init__()
        self.value = attribute.upper()
        self.section = section
        self.partial = partial
        self._raw: Optional[bytes] = None
        self._for_response: Optional['FetchAttribute'] = None

    @property
    def for_response(self) -> 'FetchAttribute':
        if self._for_response is None:
            if self.partial is None or len(self.partial) < 2:
                self._for_response = self
            else:
                self._for_response = FetchAttribute(
                    self.value, self.section, self.partial[:1])
        return self._for_response

    @property
    def set_seen(self) -> bool:
        if self.value == b'BODY' and self.section:
            return True
        elif self.value in (b'RFC822', b'RFC822.TEXT'):
            return True
        return False

    @property
    def raw(self) -> bytes:
        if self._raw is not None:
            return self._raw
        if self.value == b'BODY.PEEK':
            parts = [b'BODY']
        else:
            parts = [self.value]
        if self.section:
            parts.append(b'[')
            if self.section.parts:
                part_raw = b'.'.join(
                    [b'%i' % num for num in self.section.parts])
                parts.append(part_raw)
                if self.section.msgtext:
                    parts.append(b'.')
            if self.section.msgtext:
                parts.append(self.section.msgtext)
            if self.section.headers:
                parts.append(b' ')
                parts.append(bytes(ListP(self.section.headers)))
            parts.append(b']')
        if self.partial:
            partial = b'.'.join([b'%i' % p for p in self.partial])
            parts += [b'<', partial, b'>']
        self._raw = raw = b''.join(parts)
        return raw

    def __hash__(self):
        return hash((self.value, self.section, self.partial))

    def __eq__(self, other):
        return hash(self) == hash(other)

    def __ne__(self, other):
        return hash(self) != hash(other)

    def __lt__(self, other):
        return bytes(self.for_response) < bytes(self.for_response)

    @classmethod
    def _parse_section(cls, buf: bytes, params: Params):
        section_parts = None
        match = cls._sec_part_pattern.match(buf)
        if match:
            section_parts = frozenset(int(num) for num in
                                      match.group(1).split(b'.'))
            buf = buf[match.end(0):]
            if not match.group(2):
                return cls.Section(section_parts), buf
            elif match.group(3):
                return cls.Section(section_parts, b'MIME'), buf
        try:
            atom, after = Atom.parse(buf, params)
        except NotParseable:
            return cls.Section(section_parts), buf
        sec_msgtext = atom.value.upper()
        if sec_msgtext in (b'HEADER', b'TEXT'):
            return cls.Section(section_parts, sec_msgtext), after
        elif sec_msgtext in (b'HEADER.FIELDS', b'HEADER.FIELDS.NOT'):
            params = params.copy(list_expected=[AString])
            header_list_p, buf = ListP.parse(after, params)
            header_list = frozenset(
                [bytes(hdr).upper() for hdr in header_list_p.value])
            if not header_list:
                raise NotParseable(after)
            return cls.Section(section_parts, sec_msgtext, header_list), buf
        raise NotParseable(buf)

    @classmethod
    def parse(cls, buf: bytes, params: Params) \
            -> Tuple['FetchAttribute', bytes]:
        match = cls._attrname_pattern.match(buf)
        if not match:
            raise NotParseable(buf)
        attr = match.group(1).upper()
        after = buf[match.end(0):]
        if attr in (b'ENVELOPE', b'FLAGS', b'INTERNALDATE', b'UID', b'RFC822',
                    b'RFC822.HEADER', b'RFC822.SIZE', b'RFC822.TEXT',
                    b'BODYSTRUCTURE'):
            return cls(attr), after
        elif attr not in (b'BODY', b'BODY.PEEK'):
            raise NotParseable(buf)
        buf = after
        match = cls._section_start_pattern.match(buf)
        if not match:
            if attr == b'BODY':
                return cls(attr), buf
            else:
                raise NotParseable(buf)
        section, buf = cls._parse_section(buf[match.end(0):], params)
        match = cls._section_end_pattern.match(buf)
        if not match:
            raise NotParseable(buf)
        buf = buf[match.end(0):]
        match = cls._partial_pattern.match(buf)
        if match:
            from_, to = int(match.group(1)), int(match.group(2))
            if from_ < 0 or to <= 0 or from_ > to:
                raise NotParseable(buf)
            return cls(attr, section, (from_, to)), buf[match.end(0):]
        return cls(attr, section), buf

    def __bytes__(self):
        return self.raw
