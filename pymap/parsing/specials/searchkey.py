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

from pymap.flags import Flag
from . import Special, AString, SequenceSet
from .. import Parseable, NotParseable, UnexpectedType, Space
from ..primitives import Atom, Number, QuotedString, List

__all__ = ['SearchKey']


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
        super().__init__()
        self.key = key
        self.filter = filter
        self.inverse = inverse
        self._raw = None

    @property
    def raw(self):
        if self._raw is not None:
            return self._raw
        raise NotImplementedError

    def __hash__(self):
        return hash((self.key, self.filter, self.inverse))

    def __eq__(self, other):
        return hash(self) == hash(other)

    def __ne__(self, other):
        return hash(self) != hash(other)

    @classmethod
    def _parse_astring_filter(cls, buf, charset, **kwargs):
        ret, after = AString.parse(buf, **kwargs)
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
    def parse(cls, buf, charset=None, list_expected=None, **kwargs):
        try:
            _, buf = Space.parse(buf)
        except NotParseable:
            pass
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
