"""Utilities for managing a IMAP searches."""

from datetime import datetime
from typing import cast, FrozenSet, Tuple, Optional, Iterable

from .exceptions import SearchNotAllowed
from .interfaces.message import Message, LoadedMessage
from .parsing.specials import SearchKey, SequenceSet
from .parsing.specials.flag import Flag, Keyword, Answered, Deleted, Draft, \
    Flagged, Recent, Seen
from .selected import SelectedMailbox

__all__ = ['SearchParams', 'SearchCriteria', 'SearchCriteriaSet']


class SearchParams:
    """Defines certain parameters and routines necessary to process any
    kind of search criteria. If a parameter is not supplied, or a method not
    implemented, any search keys that require it will fail.

    Args:
        selected: The active mailbox session.
        max_seq: The highest message sequence ID in the mailbox.
        max_uid: The highest message UID in the mailbox.
        disabled: Search keys that should be disabled.

    """

    def __init__(self, selected: SelectedMailbox,
                 max_seq: int = None, max_uid: int = None,
                 disabled: Iterable[bytes] = None) -> None:
        self.selected = selected
        if max_seq is not None:
            self._max_seq = max_seq
        if max_uid is not None:
            self._max_uid = max_uid
        if disabled is not None:
            self._disabled = frozenset(disabled)

    @property
    def max_seq(self) -> int:
        if not hasattr(self, '_max_seq'):
            raise SearchNotAllowed
        return self._max_seq

    @property
    def max_uid(self) -> int:
        if not hasattr(self, '_max_uid'):
            raise SearchNotAllowed
        return self._max_uid

    @property
    def disabled(self) -> FrozenSet[bytes]:
        return getattr(self, '_disabled', frozenset())


class SearchCriteria:
    """Base class for different types of search criteria.

    Args:
        params: The parameters that may be used by some searches.

    """

    def __init__(self, params: SearchParams) -> None:
        self.params = params

    def matches(self, msg_seq: int, msg: Message) -> bool:
        """Implemented by sub-classes to define the search criteria.

        Args:
            msg_seq: The message sequence ID.
            msg: The message object.

        """
        raise NotImplementedError

    @classmethod
    def of(cls, key: SearchKey, params: SearchParams) -> 'SearchCriteria':
        """Factory method for producing a search criteria sub-class from a
        search key.

        Args:
            key: The search key defining the criteria.
            params: The parameters that may be used by some searches.

        """
        if key.value in params.disabled:
            raise SearchNotAllowed(key.value)
        elif key.inverse:
            return InverseSearchCriteria(key.not_inverse, params)
        elif key.value == b'SEQSET' and isinstance(key.filter, SequenceSet):
            return SequenceSetSearchCriteria(key.filter, params)
        elif key.value == b'KEYSET' and isinstance(key.filter, frozenset):
            keys = cast(FrozenSet[SearchKey], key.filter)
            return SearchCriteriaSet(keys, params)
        elif key.value == b'ALL':
            return AllSearchCriteria(params)
        elif key.value == b'OR':
            keys = cast(Tuple[SearchKey, SearchKey], key.filter)
            return OrSearchCriteria(keys[0], keys[1], params)
        elif key.value == b'ANSWERED':
            return HasFlagSearchCriteria(Answered, True, params)
        elif key.value == b'UNANSWERED':
            return HasFlagSearchCriteria(Answered, False, params)
        elif key.value == b'DELETED':
            return HasFlagSearchCriteria(Deleted, True, params)
        elif key.value == b'UNDELETED':
            return HasFlagSearchCriteria(Deleted, False, params)
        elif key.value == b'DRAFT':
            return HasFlagSearchCriteria(Draft, True, params)
        elif key.value == b'UNDRAFT':
            return HasFlagSearchCriteria(Draft, False, params)
        elif key.value == b'FLAGGED':
            return HasFlagSearchCriteria(Flagged, True, params)
        elif key.value == b'UNFLAGGED':
            return HasFlagSearchCriteria(Flagged, False, params)
        elif key.value == b'RECENT':
            return HasFlagSearchCriteria(Recent, True, params)
        elif key.value == b'OLD':
            return HasFlagSearchCriteria(Recent, False, params)
        elif key.value == b'SEEN':
            return HasFlagSearchCriteria(Seen, True, params)
        elif key.value == b'UNSEEN':
            return HasFlagSearchCriteria(Seen, False, params)
        elif key.value == b'KEYWORD':
            keyword = cast(Keyword, key.filter)
            return HasFlagSearchCriteria(keyword, True, params)
        elif key.value == b'UNKEYWORD':
            keyword = cast(Keyword, key.filter)
            return HasFlagSearchCriteria(keyword, False, params)
        elif key.value == b'NEW':
            return NewSearchCriteria(params)
        elif key.value == b'BEFORE':
            when = cast(datetime, key.filter)
            return DateSearchCriteria(when, '<', params)
        elif key.value == b'ON':
            when = cast(datetime, key.filter)
            return DateSearchCriteria(when, '=', params)
        elif key.value == b'SINCE':
            when = cast(datetime, key.filter)
            return DateSearchCriteria(when, '>', params)
        elif key.value == b'SENTBEFORE':
            when = cast(datetime, key.filter)
            return HeaderDateSearchCriteria(when, '<', params)
        elif key.value == b'SENTON':
            when = cast(datetime, key.filter)
            return HeaderDateSearchCriteria(when, '=', params)
        elif key.value == b'SENTSINCE':
            when = cast(datetime, key.filter)
            return HeaderDateSearchCriteria(when, '>', params)
        elif key.value == b'SMALLER':
            size = cast(int, key.filter)
            return SizeSearchCriteria(size, '<', params)
        elif key.value == b'LARGER':
            size = cast(int, key.filter)
            return SizeSearchCriteria(size, '>', params)
        elif key.value in (b'BCC', b'CC', b'FROM', b'SUBJECT', b'TO'):
            value = cast(str, key.filter)
            return EnvelopeSearchCriteria(key.value, value, params)
        elif key.value == b'HEADER':
            name, value = cast(Tuple[str, str], key.filter)
            return HeaderSearchCriteria(name, value, params)
        elif key.value in (b'BODY', b'TEXT'):
            value = cast(str, key.filter)
            return BodySearchCriteria(value, key.value == b'TEXT', params)
        raise SearchNotAllowed(key.value)


class SearchCriteriaSet(SearchCriteria):
    """Search criteria composed of a set of search criteria that must all
    match. If the set is empty, nothing will match.

    Args:
        keys: The set of search keys that must match.
        params: The parameters that may be used by some searches.

    """

    def __init__(self, keys: FrozenSet[SearchKey],
                 params: SearchParams) -> None:
        super().__init__(params)
        self.all_criteria = [SearchCriteria.of(key, params) for key in keys]

    def matches(self, msg_seq: int, msg: Message) -> bool:
        return all(crit.matches(msg_seq, msg) for crit in self.all_criteria)


class _LoadedSearchCriteria(SearchCriteria):

    @classmethod
    def _get_loaded(cls, msg: Message) -> LoadedMessage:
        if isinstance(msg, LoadedMessage):
            return cast(LoadedMessage, msg)
        else:
            raise SearchNotAllowed

    def matches(self, msg_seq: int, msg: Message) -> bool:
        raise NotImplementedError


class InverseSearchCriteria(SearchCriteria):
    """Matches only if the given search criteria does not match."""

    def __init__(self, key: SearchKey, params: SearchParams) -> None:
        super().__init__(params)
        self.key = SearchCriteria.of(key, params)

    def matches(self, msg_seq: int, msg: Message) -> bool:
        return not self.key.matches(msg_seq, msg)


class AllSearchCriteria(SearchCriteria):
    """Always matches anything."""

    def matches(self, msg_seq: int, msg: Message):
        return True


class OrSearchCriteria(SearchCriteria):
    """Matches if either of the search criteria match."""

    def __init__(self, left: SearchKey, right: SearchKey,
                 params: SearchParams) -> None:
        super().__init__(params)
        self.left = SearchCriteria.of(left, self.params)
        self.right = SearchCriteria.of(right, self.params)

    def matches(self, msg_seq: int, msg: Message) -> bool:
        return (self.left.matches(msg_seq, msg)
                or self.right.matches(msg_seq, msg))


class SequenceSetSearchCriteria(SearchCriteria):
    """Matches if the message is contained in the sequence set."""

    def __init__(self, seq_set: SequenceSet, params: SearchParams) -> None:
        super().__init__(params)
        self.seq_set = seq_set

    def matches(self, msg_seq: int, msg: Message) -> bool:
        if self.seq_set.uid:
            return self.seq_set.contains(msg.uid, self.params.max_uid)
        else:
            return self.seq_set.contains(msg_seq, self.params.max_seq)


class HasFlagSearchCriteria(SearchCriteria):
    """Matches if the message has the given flag in their permanent or
    session flag sets.

    """

    def __init__(self, flag: Flag, expected: bool,
                 params: SearchParams) -> None:
        super().__init__(params)
        self.flag = flag
        self.expected = expected

    def matches(self, msg_seq: int, msg: Message) -> bool:
        has_flag = self.flag in msg.get_flags(self.params.selected)
        expected = self.expected
        return (has_flag and expected) or (not expected and not has_flag)


class NewSearchCriteria(SearchCriteria):
    """Matches if the message is considered "new", i.e. recent and unseen."""

    def matches(self, msg_seq: int, msg: Message) -> bool:
        flags = msg.get_flags(self.params.selected)
        return Recent in flags and Seen not in flags


class DateSearchCriteria(SearchCriteria):
    """Matches by comparing against the internal date of the message."""

    def __init__(self, when: datetime, cmp: str, params: SearchParams) -> None:
        super().__init__(params)
        self.when = when.date()
        self.cmp = cmp

    @classmethod
    def _get_msg_date(cls, msg: Message) -> Optional[datetime]:
        return msg.internal_date

    def matches(self, msg_seq: int, msg: Message) -> bool:
        msg_datetime = self._get_msg_date(msg)
        if msg_datetime is None:
            return False
        msg_date = msg_datetime.date()
        if self.cmp == '<':  # BEFORE
            return msg_date < self.when
        elif self.cmp == '=':  # ON
            return msg_date == self.when
        elif self.cmp == '>':  # SINCE
            return msg_date > self.when
        raise RuntimeError  # should not happen


class HeaderDateSearchCriteria(DateSearchCriteria, _LoadedSearchCriteria):
    """Matches by comparing against the ``Date:`` header of the message."""

    @classmethod
    def _get_msg_date(cls, msg: Message) -> Optional[datetime]:
        loaded = cls._get_loaded(msg)
        envelope = loaded.get_envelope_structure()
        return envelope.date.datetime if envelope.date else None


class SizeSearchCriteria(_LoadedSearchCriteria):
    """Matches by comparing against the size of the message."""

    def __init__(self, size: int, cmp: str, params: SearchParams) -> None:
        super().__init__(params)
        self.size = size
        self.cmp = cmp

    def matches(self, msg_seq: int, msg: Message) -> bool:
        loaded = self._get_loaded(msg)
        size = loaded.get_size()
        if self.cmp == '<':
            return size < self.size
        elif self.cmp == '>':
            return size > self.size
        raise RuntimeError  # should not happen


class EnvelopeSearchCriteria(_LoadedSearchCriteria):
    """Matches by checking for strings withing various fields of the
    envelope structure.

    """

    def __init__(self, key: bytes, value: str, params: SearchParams) -> None:
        super().__init__(params)
        self.key = key
        self.value = value

    def matches(self, msg_seq: int, msg: Message) -> bool:
        loaded = self._get_loaded(msg)
        envelope = loaded.get_envelope_structure()
        if self.key == b'BCC':
            if not envelope.bcc:
                return False
            return any(self.value in str(bcc) for bcc in envelope.bcc)
        elif self.key == b'CC':
            if not envelope.cc:
                return False
            return any(self.value in str(cc) for cc in envelope.cc)
        elif self.key == b'FROM':
            if not envelope.from_:
                return False
            return any(self.value in str(from_) for from_ in envelope.from_)
        elif self.key == b'SUBJECT':
            if not envelope.subject:
                return False
            return self.value in str(envelope.subject)
        elif self.key == b'TO':
            if not envelope.to:
                return False
            return any(self.value in str(to) for to in envelope.to)
        raise RuntimeError


class HeaderSearchCriteria(_LoadedSearchCriteria):
    """Matches if the message has a header containing a value."""

    def __init__(self, name: str, value: str, params: SearchParams) -> None:
        super().__init__(params)
        self.name = bytes(name, 'ascii', 'ignore')
        self.value = value

    def matches(self, msg_seq: int, msg: Message) -> bool:
        loaded = self._get_loaded(msg)
        values = loaded.get_header(self.name)
        return any(self.value in str(value) for value in values)


class BodySearchCriteria(_LoadedSearchCriteria):
    """Matches if the message body contains a value."""

    def __init__(self, value: str, with_headers: bool,
                 params: SearchParams) -> None:
        super().__init__(params)
        self.with_headers = with_headers
        self.value = bytes(value, 'utf-8')

    def matches(self, msg_seq: int, msg: Message) -> bool:
        loaded = self._get_loaded(msg)
        data = loaded.get_body() if self.with_headers else loaded.get_text()
        return data is not None and self.value in data
