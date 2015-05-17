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

import re

from .. import NotParseable
from ..primitives import Atom, List
from . import Special, AString

__all__ = ['FetchAttribute']


class FetchAttribute(Special):
    """Represents an attribute that should be fetched for each message in the
    sequence set of a FETCH command on an IMAP stream.

    :param byte attribute: Fetch attribute name.

    """

    _attrname_pattern = re.compile(br' *([^\s\[\<\(\)]+)')
    _section_start_pattern = re.compile(br' *\[ *')
    _section_end_pattern = re.compile(br' *\] *')
    _partial_pattern = re.compile(br'\< *(\d+) *\. *(\d+) *\>')

    _sec_part_pattern = \
        re.compile(br'(\d+ *(?:\. *\d+)*) *(\.)? *(MIME)?', re.I)

    def __init__(self, attribute, section=None, partial=None, raw=None):
        super().__init__()
        self.attribute = attribute.upper()
        self.section = section
        self.partial = partial
        self._raw = raw

    def copy(self, new_attribute=None):
        attr = new_attribute or self.attribute
        return FetchAttribute(attr, self.section, self.partial)

    @property
    def raw(self):
        if self._raw is not None:
            return self._raw
        parts = [self.attribute]
        if self.section:
            parts.append(b'[')
            if self.section[0]:
                part_raw = b'.'.join([bytes(str(num), 'ascii')
                                      for num in self.section[0]])
                parts.append(part_raw)
                if self.section[1]:
                    parts.append(b'.')
            if self.section[1]:
                parts.append(self.section[1])
            if self.section[2]:
                parts.append(b' ')
                parts.append(bytes(List(self.section[2])))
            parts.append(b']')
        if self.partial:
            parts += [b'<', self.partial[0], b'.', self.partial[1], b'>']
        self._raw = raw = b''.join(parts)
        return raw

    def __hash__(self):
        return hash((self.attribute, self.section, self.partial))

    def __eq__(self, other):
        return hash(self) == hash(other)

    def __ne__(self, other):
        return hash(self) != hash(other)

    @classmethod
    def _parse_section(cls, buf, **kwargs):
        section_parts = None
        match = cls._sec_part_pattern.match(buf)
        if match:
            section_parts = [int(num) for num in match.group(1).split(b'.')]
            buf = buf[match.end(0):]
            if not match.group(2):
                return (section_parts, None, None), buf
            elif match.group(3):
                return (section_parts, b'MIME', None), buf
        try:
            atom, after = Atom.parse(buf)
        except NotParseable:
            return (section_parts, None, None), buf
        sec_msgtext = atom.value.upper()
        if sec_msgtext in (b'HEADER', b'TEXT'):
            return (section_parts, sec_msgtext, None), after
        elif sec_msgtext in (b'HEADER.FIELDS', b'HEADER.FIELDS.NOT'):
            kwargs_copy = kwargs.copy()
            kwargs_copy['list_expected'] = [AString]
            header_list, buf = List.parse(after, **kwargs_copy)
            header_list = frozenset([hdr.value.upper()
                                     for hdr in header_list.value])
            if not header_list:
                raise NotParseable(after)
            return (section_parts, sec_msgtext, header_list), buf
        raise NotParseable(buf)

    @classmethod
    def parse(cls, buf, **kwargs):
        buf = memoryview(buf)
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
        section, buf = cls._parse_section(buf[match.end(0):], **kwargs)
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
