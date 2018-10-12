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
from datetime import datetime
from typing import TYPE_CHECKING, Optional, Tuple, Union, Mapping, Sequence

from pymap.parsing.specials import Flag
from .astring import AString
from .sequenceset import SequenceSet
from .. import Parseable, NotParseable, UnexpectedType, Space, Params, Special
from ..primitives import Atom, Number, QuotedString, ListP

__all__ = ['SearchKey']

if TYPE_CHECKING:
    _FilterType = Union[Tuple['SearchKey', 'SearchKey'],
                        Mapping[str, str], Sequence[Parseable],
                        SequenceSet, Flag, datetime, int, str]


class SearchKey(Special[Optional[bytes]]):
    """Represents a search key given to the SEARCH command on an IMAP stream.

    """

    _not_pattern = re.compile(br'NOT +', re.I)

    def __init__(self, key: Optional[bytes],
                 filter_: '_FilterType' = None,
                 inverse: bool = False) -> None:
        super().__init__()
        self.value = key
        self.filter = filter_
        self.inverse = inverse

    @property
    def __bytes__(self):
        raise NotImplementedError

    def __hash__(self):
        return hash((self.value, self.filter, self.inverse))

    def __eq__(self, other):
        return hash(self) == hash(other)

    def __ne__(self, other):
        return hash(self) != hash(other)

    @classmethod
    def _parse_astring_filter(cls, buf: bytes, params: Params):
        ret, after = AString.parse(buf, params)
        return ret.value.decode(params.charset or 'ascii'), after

    @classmethod
    def _parse_date_filter(cls, buf: bytes, params: Params):
        params_copy = params.copy(expected=[Atom, QuotedString])
        atom, after = Parseable.parse(buf, params_copy)
        try:
            date = datetime.strptime(str(atom.value, 'ascii'), '%d-%b-%Y')
        except ValueError:
            raise NotParseable(buf)
        return date, after

    @classmethod
    def parse(cls, buf: bytes, params: Params) -> Tuple['SearchKey', bytes]:
        try:
            _, buf = Space.parse(buf, params)
        except NotParseable:
            pass
        inverse = False
        match = cls._not_pattern.match(buf)
        if match:
            inverse = True
            buf = buf[match.end(0):]
        try:
            seq_set, buf = SequenceSet.parse(buf, params)
        except NotParseable:
            pass
        else:
            return cls(None, seq_set, inverse), buf
        try:
            params_copy = params.copy(list_expected=[SearchKey])
            key_list, buf = ListP.parse(buf, params_copy)
        except UnexpectedType:
            raise
        except NotParseable:
            pass
        else:
            return cls(None, key_list.value, inverse), buf
        atom, after = Atom.parse(buf, params)
        key = atom.value.upper()
        if key in (b'ALL', b'ANSWERED', b'DELETED', b'FLAGGED', b'NEW', b'OLD',
                   b'RECENT', b'SEEN', b'UNANSWERED', b'UNDELETED',
                   b'UNFLAGGED', b'UNSEEN', b'DRAFT', b'UNDRAFT'):
            return cls(key, inverse=inverse), after
        elif key in (
                b'BCC', b'BODY', b'CC', b'FROM', b'SUBJECT', b'TEXT', b'TO'):
            _, buf = Space.parse(after, params)
            filter_, buf = cls._parse_astring_filter(buf, params)
            return cls(key, filter_, inverse), buf
        elif key in (b'BEFORE', b'ON', b'SINCE', b'SENTBEFORE', b'SENTON',
                     b'SENTSINCE'):
            _, buf = Space.parse(after, params)
            filter_, buf = cls._parse_date_filter(buf, params)
            return cls(key, filter_, inverse), buf
        elif key in (b'KEYWORD', b'UNKEYWORD'):
            _, buf = Space.parse(after, params)
            atom, buf = Atom.parse(buf, params)
            return cls(key, Flag(atom.value), inverse), buf
        elif key in (b'LARGER', b'SMALLER'):
            _, buf = Space.parse(after, params)
            num, buf = Number.parse(buf, params)
            return cls(key, num.value, inverse), buf
        elif key == b'UID':
            _, buf = Space.parse(after, params)
            seq_set, buf = SequenceSet.parse(buf, params.copy(uid=True))
            return cls(None, seq_set, inverse), buf
        elif key == b'HEADER':
            _, buf = Space.parse(after, params)
            header_field, buf = cls._parse_astring_filter(buf, params)
            _, buf = Space.parse(buf, params)
            header_value, buf = cls._parse_astring_filter(buf, params)
            return cls(key, {header_field: header_value}, inverse), buf
        elif key == b'OR':
            _, buf = Space.parse(after, params)
            or1, buf = SearchKey.parse(buf, params)
            _, buf = Space.parse(buf, params)
            or2, buf = SearchKey.parse(buf, params)
            return cls(key, (or1, or2), inverse), buf
        raise NotParseable(buf)
