
from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import datetime
from typing import Any, TypeVar, Union

from .astring import AString
from .fetchattr import FetchRequirement
from .flag import Flag
from .objectid import ObjectId
from .sequenceset import SequenceSet
from .. import Params, Parseable, ExpectedParseable, Space
from ..exceptions import NotParseable, UnexpectedType
from ..primitives import Atom, Number, QuotedString, List
from ...bytes import rev

__all__ = ['SearchKey']

_FilterType = Union[tuple['SearchKey', 'SearchKey'], tuple[str, str],
                    Sequence['SearchKey'], SequenceSet, Flag, ObjectId,
                    datetime, int, str]
_FilterT = TypeVar('_FilterT', bound=_FilterType)


class SearchKey(Parseable[bytes]):
    """Represents a search key given to the SEARCH command on an IMAP stream.

    Args:
        key: The search key.
        filter_: The filter object, used by most search keys.
        inverse: If the search key was inverted with ``NOT``.

    Args:
        filter_: The filter object, used by most search keys.
        inverse: If the search key was inverted with ``NOT``.

    """

    _not_pattern = rev.compile(br'NOT +', re.I)

    def __init__(self, key: bytes,
                 filter_: _FilterType = None,
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
    def value_str(self) -> str:
        """The search key, as a string."""
        return self.key.decode('ascii')

    @property
    def requirement(self) -> FetchRequirement:
        """Indicates the data required to fulfill this search key."""
        key_name = self.key
        if key_name == b'ALL':
            return FetchRequirement.NONE
        elif key_name == b'KEYSET':
            keyset_reqs = {key.requirement for key in self.filter_key_set}
            return FetchRequirement.reduce(keyset_reqs)
        elif key_name == b'OR':
            left, right = self.filter_key_or
            key_or_reqs = {left.requirement, right.requirement}
            return FetchRequirement.reduce(key_or_reqs)
        elif key_name in (b'SENTBEFORE', b'SENTON', b'SENTSINCE', b'BCC',
                          b'CC', b'FROM', b'SUBJECT', b'TO', b'HEADER'):
            return FetchRequirement.HEADER
        elif key_name in (b'BODY', b'TEXT', b'LARGER', b'SMALLER'):
            return FetchRequirement.CONTENT
        else:
            return FetchRequirement.METADATA

    @property
    def not_inverse(self) -> SearchKey:
        """Return a copy of the search key with :attr:`.inverse` flipped."""
        return SearchKey(self.value, self.filter, not self.inverse)

    def _get_filter(self, cls) -> Any:
        if not isinstance(self.filter, cls):
            raise TypeError(self.filter)
        return self.filter

    @property
    def filter_sequence_set(self) -> SequenceSet:
        return self._get_filter(SequenceSet)

    @property
    def filter_key_set(self) -> frozenset[SearchKey]:
        return self._get_filter(frozenset)

    @property
    def filter_key_or(self) -> tuple[SearchKey, SearchKey]:
        return self._get_filter(tuple)

    @property
    def filter_flag(self) -> Flag:
        return self._get_filter(Flag)

    @property
    def filter_datetime(self) -> datetime:
        return self._get_filter(datetime)

    @property
    def filter_int(self) -> int:
        return self._get_filter(int)

    @property
    def filter_str(self) -> str:
        return self._get_filter(str)

    @property
    def filter_header(self) -> tuple[str, str]:
        return self._get_filter(tuple)

    @property
    def filter_object_id(self) -> ObjectId:
        return self._get_filter(ObjectId)

    def __bytes__(self) -> bytes:
        raise NotImplementedError

    def __hash__(self) -> int:
        return hash((self.value, self.filter, self.inverse))

    def __eq__(self, other) -> bool:
        if isinstance(other, SearchKey):
            return hash(self) == hash(other)
        return super().__eq__(other)

    def __ne__(self, other) -> bool:
        if isinstance(other, SearchKey):
            return hash(self) != hash(other)
        return super().__ne__(other)

    @classmethod
    def _parse_astring_filter(cls, buf: memoryview, params: Params) \
            -> tuple[str, memoryview]:
        ret, after = AString.parse(buf, params)
        return ret.value.decode(params.charset or 'ascii'), after

    @classmethod
    def _parse_date_filter(cls, buf: memoryview, params: Params) \
            -> tuple[datetime, memoryview]:
        params_copy = params.copy(expected=[Atom, QuotedString])
        atom, after = ExpectedParseable.parse(buf, params_copy)
        date_str = str(atom.value, 'ascii', 'ignore')
        try:
            date = datetime.strptime(date_str, '%d-%b-%Y')
        except ValueError:
            raise NotParseable(buf)
        return date, after

    @classmethod
    def parse(cls, buf: memoryview, params: Params) \
            -> tuple[SearchKey, memoryview]:
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
            key_list_p, buf = List.parse(buf, params_copy)
        except UnexpectedType:
            raise
        except NotParseable:
            pass
        else:
            key_list = key_list_p.get_as(SearchKey)
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
            filter_str, buf = cls._parse_astring_filter(buf, params)
            return cls(key, filter_str, inverse), buf
        elif key in (b'EMAILID', b'THREADID'):
            _, buf = Space.parse(after, params)
            filter_id, buf = ObjectId.parse(buf, params)
            return cls(key, filter_id, inverse), buf
        elif key in (b'BEFORE', b'ON', b'SINCE', b'SENTBEFORE', b'SENTON',
                     b'SENTSINCE'):
            _, buf = Space.parse(after, params)
            filter_date, buf = cls._parse_date_filter(buf, params)
            return cls(key, filter_date, inverse), buf
        elif key in (b'KEYWORD', b'UNKEYWORD'):
            _, buf = Space.parse(after, params)
            flag, after_buf = Flag.parse(buf, params)
            if flag.is_system:
                raise NotParseable(buf)
            return cls(key, flag, inverse), after_buf
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
