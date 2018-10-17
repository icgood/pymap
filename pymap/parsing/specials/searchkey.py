import re
from datetime import datetime
from typing import TYPE_CHECKING, cast, Tuple, Union, Sequence

from .astring import AString
from .flag import Keyword
from .sequenceset import SequenceSet
from .. import ExpectedParseable, NotParseable, UnexpectedType, Space, \
    Params, Special
from ..primitives import Atom, Number, QuotedString, ListP

__all__ = ['SearchKey']

if TYPE_CHECKING:
    _FilterType = Union[Tuple['SearchKey', 'SearchKey'], Tuple[str, str],
                        Sequence['SearchKey'], SequenceSet, Keyword,
                        datetime, int, str]


class SearchKey(Special[bytes]):
    """Represents a search key given to the SEARCH command on an IMAP stream.

    Args:
        key: The search key.
        filter_: The filter object, used by most search keys.
        inverse: If the search key was inverted with ``NOT``.

    Args:
        filter_: The filter object, used by most search keys.
        inverse: If the search key was inverted with ``NOT``.

    """

    _not_pattern = re.compile(br'NOT +', re.I)

    def __init__(self, key: bytes,
                 filter_: '_FilterType' = None,
                 inverse: bool = False) -> None:
        super().__init__()
        self.key = key
        self.filter = filter_
        self.inverse = inverse

    @property
    def value(self) -> bytes:
        """The search key."""
        return self.key

    @property
    def not_inverse(self) -> 'SearchKey':
        """Return a copy of the search key with :attr:`.inverse` flipped."""
        return SearchKey(self.value, self.filter, not self.inverse)

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
        atom, after = ExpectedParseable.parse(buf, params_copy)
        date_str = str(atom.value, 'ascii', 'ignore')
        try:
            date = datetime.strptime(date_str, '%d-%b-%Y')
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
            return cls(b'SEQSET', seq_set, inverse), buf
        try:
            params_copy = params.copy(list_expected=[SearchKey])
            key_list_p, buf = ListP.parse(buf, params_copy)
        except UnexpectedType:
            raise
        except NotParseable:
            pass
        else:
            key_list = cast(Sequence[SearchKey], key_list_p.value)
            return cls(b'KEYSET', key_list, inverse), buf
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
            keyword, buf = Keyword.parse(buf, params)
            return cls(key, keyword, inverse), buf
        elif key in (b'LARGER', b'SMALLER'):
            _, buf = Space.parse(after, params)
            num, buf = Number.parse(buf, params)
            return cls(key, num.value, inverse), buf
        elif key == b'UID':
            _, buf = Space.parse(after, params)
            seq_set, buf = SequenceSet.parse(buf, params.copy(uid=True))
            return cls(b'SEQSET', seq_set, inverse), buf
        elif key == b'HEADER':
            _, buf = Space.parse(after, params)
            header_field, buf = cls._parse_astring_filter(buf, params)
            _, buf = Space.parse(buf, params)
            header_value, buf = cls._parse_astring_filter(buf, params)
            return cls(key, (header_field, header_value), inverse), buf
        elif key == b'OR':
            _, buf = Space.parse(after, params)
            or1, buf = SearchKey.parse(buf, params)
            _, buf = Space.parse(buf, params)
            or2, buf = SearchKey.parse(buf, params)
            return cls(key, (or1, or2), inverse), buf
        raise NotParseable(buf)
