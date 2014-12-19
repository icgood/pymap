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
from datetime import datetime

from . import Parseable, NotParseable, UnexpectedType, Space
from .primitives import Atom, Number, String, QuotedString, List

__all__ = ['Special', 'InvalidContent', 'AString', 'Tag', 'Mailbox',
           'DateTime', 'Flag', 'StatusAttribute', 'SequenceSet',
           'FetchAttribute', 'SearchKey']


class InvalidContent(NotParseable, ValueError):
    """Indicates the type of the parsed content was correct, but something
    about the content did not fit what was expected by the special type.

    """
    pass


class Special(Parseable):
    """Base class for special data objects in an IMAP stream.

    """
    pass


class AString(Special):
    """Represents a string that may have quotes (like a quoted-string) or may
    not (like an atom).  Additionally allows the closing square bracket (``]``)
    character in the unquoted form.

    :param bytes string: The parsed string.

    """

    _pattern = re.compile(br'[\x21\x23\x24\x26\x27\x2B-\x5B'
                          br'\x5D\x5E-\x7A\x7C\x7E]+')

    def __init__(self, string, raw=None):
        super(AString, self).__init__()
        self.value = string
        self._raw = raw

    @classmethod
    def parse(cls, buf, **kwargs):
        buf = memoryview(buf)
        start = cls._whitespace_length(buf)
        match = cls._pattern.match(buf, start)
        if match:
            buf = buf[match.end(0):]
            return cls(match.group(0), match.group(0)), buf
        string, buf = String.parse(buf)
        return cls(string.value, bytes(string)), buf

    def __bytes__(self):
        if self._raw is not None:
            return self._raw
        match = self._pattern.fullmatch(self.value)
        if match:
            return self.value
        else:
            return bytes(QuotedString(self.value))


class Tag(Special):
    """Represents the tag prefixed to every client command in an IMAP stream.

    :param bytes tag: The contents of the tag.

    """

    _pattern = re.compile(br'[\x21\x23\x24\x26\x27\x2C-\x5B'
                          br'\x5D\x5E-\x7A\x7C\x7E]+')

    def __init__(self, tag):
        super(Tag, self).__init__()
        self.value = tag

    @classmethod
    def parse(cls, buf, **kwargs):
        buf = memoryview(buf)
        start = cls._whitespace_length(buf)
        match = cls._pattern.match(buf, start)
        if not match:
            raise NotParseable(buf)
        return cls(match.group(0)), buf[match.end(0):]

    def __bytes__(self):
        return self.value


class Mailbox(Special):
    """Represents a mailbox data object from an IMAP stream.

    :param str mailbox: The mailbox string.

    """

    def __init__(self, mailbox):
        super(Mailbox, self).__init__()
        self.value = mailbox

    @classmethod
    def _modified_b64encode(cls, src):
        # Inspired by Twisted Python's implementation:
        #   https://twistedmatrix.com/trac/browser/trunk/LICENSE
        src_utf7 = src.encode('utf-7')
        return src_utf7[1:-1].replace(b'/', b',')

    @classmethod
    def _modified_b64decode(cls, src):
        # Inspired by Twisted Python's implementation:
        #   https://twistedmatrix.com/trac/browser/trunk/LICENSE
        src_utf7 = b'+' + src.replace(b',', b'/') + b'-'
        return src_utf7.decode('utf-7')

    @classmethod
    def encode_name(cls, mailbox):
        """Encode the mailbox name using the modified UTF-7 specification for
        IMAP.

        :param str mailbox: The name of the mailbox to encode.
        :rtype: bytes

        """
        ret = bytearray()
        is_usascii = True
        for i, symbol in enumerate(mailbox):
            charpoint = ord(symbol)
            if is_usascii:
                if charpoint == 0x26:
                    ret.extend(b'&-')
                elif charpoint >= 0x20 and charpoint <= 0x7e:
                    ret.append(charpoint)
                else:
                    encode_start = i
                    is_usascii = False
            else:
                if charpoint >= 0x20 and charpoint <= 0x7e:
                    to_encode = mailbox[encode_start:i]
                    encoded = cls._modified_b64encode(to_encode)
                    ret.append(0x26)
                    ret.extend(encoded)
                    ret.extend((0x2d, charpoint))
                    is_usascii = True
        if not is_usascii:
            to_encode = mailbox[encode_start:]
            encoded = cls._modified_b64encode(to_encode)
            ret.append(0x26)
            ret.extend(encoded)
            ret.append(0x2d)
        return bytes(ret)

    @classmethod
    def decode_name(cls, encoded_mailbox):
        """Decode the mailbox name using the modified UTF-7 specification for
        IMAP.

        :param bytes encoded_mailbox: The encoded name of the mailbox to
                                      decode.
        :rtype: str

        """
        parts = []
        is_usascii = True
        buf = memoryview(encoded_mailbox)
        while buf:
            byte = buf[0]
            if is_usascii:
                if buf[0:2] == b'&-':
                    parts.append('&')
                    buf = buf[2:]
                elif byte == 0x26:
                    is_usascii = False
                    buf = buf[1:]
                else:
                    parts.append(chr(byte))
                    buf = buf[1:]
            else:
                for i, byte in enumerate(buf):
                    if byte == 0x2d:
                        to_decode = buf[:i].tobytes()
                        decoded = cls._modified_b64decode(to_decode)
                        parts.append(decoded)
                        buf = buf[i+1:]
                        is_usascii = True
                        break
        if not is_usascii:
            to_decode = buf.tobytes()
            decoded = cls._modified_b64decode(to_decode)
            parts.append(decoded)
        return ''.join(parts)

    @classmethod
    def parse(cls, buf, **kwargs):
        atom, buf = AString.parse(buf)
        mailbox = atom.value
        if mailbox.upper() == b'INBOX':
            return cls('INBOX'), buf
        return cls(cls.decode_name(mailbox)), buf

    def __bytes__(self):
        return self.encode_name(self.value)


class DateTime(Special):
    """Represents a date-time quoted string from an IMAP stream.

    :param datetime when: The resulting :py:class:`~datetime.datetime` object.
    :param bytes raw: Provide the pre-computed bytes representation of
                      ``when``.

    """

    def __init__(self, when, raw=None):
        super(DateTime, self).__init__()
        self.when = when
        self._raw = raw or bytes(when.strftime('%d-%b-%Y %X %z'), 'ascii')

    @classmethod
    def parse(cls, buf, **kwargs):
        string, after = QuotedString.parse(buf)
        try:
            when_str = str(string.value, 'ascii')
            when = datetime.strptime(when_str, '%d-%b-%Y %X %z')
        except (UnicodeDecodeError, ValueError):
            raise InvalidContent(buf)
        return cls(when, string.value), after

    def __byte__(self):
        return b'"' + self._raw + b'"'


class Flag(Special):
    """Represents a message flag from an IMAP stream.

    :param str flag: The flag or keyword string. For system flags, this will
                     start with a backslash (``\``).

    """

    def __init__(self, flag):
        super(Flag, self).__init__()
        self.value = self._capitalize(flag)

    def _capitalize(self, value):
        if value.startswith(b'\\'):
            return b'\\' + value[1:].capitalize()
        return value

    def __eq__(self, other):
        if isinstance(other, Flag):
            return self.value == other.value
        elif isinstance(other, bytes):
            return self.value == self._capitalize(other)
        elif isinstance(other, str):
            other = bytes(other, 'ascii')
            return self.value == self._capitalize(other)
        return NotImplemented

    def __ne__(self, other):
        return not (self == other)

    @classmethod
    def parse(cls, buf, **kwargs):
        try:
            _, buf = Space.parse(buf)
        except NotParseable:
            pass
        if buf and buf[0] == 0x5c:
            atom, buf = Atom.parse(buf[1:])
            return cls(b'\\' + atom.value), buf
        else:
            atom, buf = Atom.parse(buf)
            return cls(atom.value), buf

    def __bytes__(self):
        return self.value


class StatusAttribute(Special):
    """Represents a status attribute from an IMAP stream.

    :param str status: The status attribute name.

    """

    _statuses = set([b'MESSAGES', b'RECENT', b'UIDVALIDITY', b'UNSEEN'])

    def __init__(self, status):
        super(StatusAttribute, self).__init__()
        self.value = status.upper()

    @classmethod
    def parse(cls, buf, **kwargs):
        try:
            _, buf = Space.parse(buf)
        except NotParseable:
            pass
        atom, after = Atom.parse(buf)
        if atom.value.upper() not in cls._statuses:
            raise InvalidContent(buf)
        return cls(atom.value), after

    def __bytes__(self):
        return self.value


class SequenceSet(Special):
    """Represents a sequence set from an IMAP stream.

    :param list sequences: List of items where each item is either a number, an
                           asterisk (``*``), or a two-item tuple where each
                           part is either a number or an asterisk. E.g.
                           ``[13, '*', ('*', 26), (50, '*')]``.

    """

    _num_pattern = re.compile(br'\d+')

    def __init__(self, sequences):
        super(SequenceSet, self).__init__()
        self.sequences = sequences
        parts = []
        for group in sequences:
            if isinstance(group, tuple):
                left = bytes(str(group[0]), 'ascii')
                right = bytes(str(group[1]), 'ascii')
                parts.append(left + b':' + right)
            else:
                parts.append(bytes(str(group), 'ascii'))
        self._raw = b','.join(parts)

    def contains(self, num, max_value):
        for group in self.sequences:
            if group == '*' and num == max_value:
                return True
            elif isinstance(group, tuple):
                one, two = group
                if one == '*':
                    group = max_value, two
                if two == '*':
                    group = one, max_value
                high = max(*group)
                low = min(*group)
                if num >= low and num <= high:
                    return True
            elif num == group:
                return True
        return False

    @classmethod
    def _parse_part(cls, buf):
        item1 = None
        if buf and buf[0] == 0x2a:
            item1 = '*'
            buf = buf[1:]
        else:
            match = cls._num_pattern.match(buf)
            if match:
                buf = buf[match.end(0):]
                item1 = int(match.group(0))
        if item1 is None:
            raise NotParseable(buf)
        if buf and buf[0] == 0x3a:
            buf = buf[1:]
            if buf and buf[0] == 0x2a:
                return (item1, '*'), buf[1:]
            match = cls._num_pattern.match(buf)
            if match:
                buf = buf[match.end(0):]
                return (item1, int(match.group(0))), buf
            raise NotParseable(buf)
        return item1, buf

    @classmethod
    def parse(cls, buf, **kwargs):
        try:
            _, buf = Space.parse(buf)
        except NotParseable:
            pass
        sequences = []
        while buf:
            item, buf = cls._parse_part(buf)
            sequences.append(item)
            if buf and buf[0] != 0x2c:
                break
            buf = buf[1:]
        if not sequences:
            raise NotParseable(buf)
        return cls(sequences), buf

    def __bytes__(self):
        return self._raw


class FetchAttribute(Special):
    """Represents an attribute that should be fetched for each message in the
    sequence set of a FETCH command on an IMAP stream.

    :param byte attribute: Fetch attribute name.

    """

    _attrname_pattern = re.compile(br' *([^ \[\<]+)')
    _section_start_pattern = re.compile(br' *\[ *')
    _section_end_pattern = re.compile(br' *\] *')
    _partial_pattern = re.compile(br'\< *(\d+) *\. *(\d+) *\>')

    _sec_part_pattern = re.compile(br'(\d+ *(?:\. *\d+)*) *(\.)? *(MIME)?', re.I)
    _sec_msgtext_pattern = re.compile(br'')

    def __init__(self, attribute, section=None, partial=None, raw=None):
        super(FetchAttribute, self).__init__()
        self.attribute = attribute.upper()
        self.section = section
        self.partial = partial
        self._raw = raw

    @property
    def raw(self):
        if self._raw is not None:
            return self._raw
        raise NotImplementedError()

    @classmethod
    def _parse_section(cls, buf):
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
            header_list, buf = List.parse(after, list_expected=[AString])
            header_list = [hdr.value.upper() for hdr in header_list.value]
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
        section, buf = cls._parse_section(buf[match.end(0):])
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


class SearchKey(Special):
    """Represents a search key given to the SEARCH command on an IMAP stream.

    :param bytes key: The name of the search key. This value may be ``None`` if
                      the filter is a :class:`SequenceSet` or if the filter is
                      a list of :class:`SearchKey` objects.
    :param filter: A possible filter to narrow down the key. The search ``key``
                   dictates what the type of this value will be.
    :param bool inverse: If the ``NOT`` keyword was used to inverse the set.

    """

    _not_pattern = re.compile(br'NOT +', re.I)

    def __init__(self, key, filter=None, inverse=False, raw=None):
        super(SearchKey, self).__init__()
        self.key = key
        self.filter = filter
        self.inverse = inverse
        self._raw = None

    @property
    def raw(self):
        if self._raw is not None:
            return self._raw
        raise NotImplementedError

    @classmethod
    def _parse_astring_filter(cls, buf, charset, **kwargs):
        ret, after = Parseable.parse(buf, expected=[Atom, String], **kwargs)
        return ret.value.decode(charset or 'ascii'), after

    @classmethod
    def _parse_date_filter(cls, buf):
        atom, after = Parseable.parse(buf, expected=[Atom, QuotedString])
        try:
            date = datetime.strptime(str(atom.value, 'ascii'), '%d-%b-%Y')
        except ValueError:
            raise NotParseable(buf)
        return date, after

    @classmethod
    def parse(cls, buf, charset=None, **kwargs):
        buf = memoryview(buf)
        inverse = False
        match = cls._not_pattern.match(buf)
        if match:
            inverse = True
            buf = buf[match.end(0):]
        try:
            seq_set, buf = SequenceSet.parse(buf)
        except NotParseable:
            pass
        else:
            return cls(None, seq_set, inverse), buf
        try:
            key_list, buf = List.parse(buf, list_expected=[SearchKey],
                                       charset=charset, **kwargs)
        except UnexpectedType:
            raise
        except NotParseable:
            pass
        else:
            return cls(None, key_list.value, inverse), buf
        atom, after = Atom.parse(buf)
        key = atom.value.upper()
        if key in (b'ALL', b'ANSWERED', b'DELETED', b'FLAGGED', b'NEW', b'OLD',
                   b'RECENT', b'SEEN', b'UNANSWERED', b'UNDELETED',
                   b'UNFLAGGED', b'UNSEEN', b'DRAFT', b'UNDRAFT'):
            return cls(key, inverse=inverse), after
        elif key in (b'BCC', b'BODY', b'CC', b'FROM', b'SUBJECT',
                   b'TEXT', b'TO'):
            _, buf = Space.parse(after)
            filter, buf = cls._parse_astring_filter(buf, charset, **kwargs)
            return cls(key, filter, inverse), buf
        elif key in (b'BEFORE', b'ON', b'SINCE',
                     b'SENTBEFORE', b'SENTON', b'SENTSINCE'):
            _, buf = Space.parse(after)
            filter, buf = cls._parse_date_filter(buf)
            return cls(key, filter, inverse), buf
        elif key in (b'KEYWORD', b'UNKEYWORD'):
            _, buf = Space.parse(after)
            atom, buf = Atom.parse(buf)
            return cls(key, Flag(atom.value), inverse), buf
        elif key in (b'LARGER', b'SMALLER'):
            _, buf = Space.parse(after)
            num, buf = Number.parse(buf)
            return cls(key, num.value, inverse), buf
        elif key == b'UID':
            _, buf = Space.parse(after)
            seq_set, buf = SequenceSet.parse(buf)
            return cls(key, seq_set, inverse), buf
        elif key == b'HEADER':
            _, buf = Space.parse(after)
            header_field, buf = cls._parse_astring_filter(buf, charset)
            _, buf = Space.parse(buf)
            header_value, buf = cls._parse_astring_filter(buf, charset)
            return cls(key, {header_field: header_value}, inverse), buf
        elif key == b'OR':
            _, buf = Space.parse(after)
            or1, buf = SearchKey.parse(buf, charset=charset)
            _, buf = Space.parse(buf)
            or2, buf = SearchKey.parse(buf, charset=charset)
            return cls(key, (or1, or2), inverse), buf
        raise NotParseable(buf)
