"""Utilities for managing a IMAP searches."""

from abc import abstractmethod, ABCMeta
from datetime import datetime
from typing import FrozenSet, Optional, Iterable

from .exceptions import SearchNotAllowed
from .flags import SessionFlags
from .interfaces.message import MessageInterface
from .parsing.specials import SearchKey, SequenceSet
from .parsing.specials.flag import Flag, Answered, Deleted, Draft, Flagged, \
    Recent, Seen
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

    __slots__ = ['selected', '_max_seq', '_max_uid', '_disabled']

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
    def session_flags(self) -> SessionFlags:
        return self.selected.session_flags

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


class SearchCriteria(metaclass=ABCMeta):
    """Base class for different types of search criteria.

    Args:
        params: The parameters that may be used by some searches.

    """

    def __init__(self, params: SearchParams) -> None:
        self.params = params

    @abstractmethod
    def matches(self, msg_seq: int, msg: MessageInterface) -> bool:
        """Implemented by sub-classes to define the search criteria.

        Args:
            msg_seq: The message sequence ID.
            msg: The message object.

        """
        ...

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
        elif key.value == b'SEQSET':
            return SequenceSetSearchCriteria(key.filter_sequence_set, params)
        elif key.value == b'KEYSET':
            return SearchCriteriaSet(key.filter_key_set, params)
        elif key.value == b'ALL':
            return AllSearchCriteria(params)
        elif key.value == b'OR':
            left_key, right_key = key.filter_key_or
            return OrSearchCriteria(left_key, right_key, params)
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
            return HasFlagSearchCriteria(key.filter_flag, True, params)
        elif key.value == b'UNKEYWORD':
            return HasFlagSearchCriteria(key.filter_flag, False, params)
        elif key.value == b'NEW':
            return NewSearchCriteria(params)
        elif key.value == b'BEFORE':
            return DateSearchCriteria(key.filter_datetime, '<', params)
        elif key.value == b'ON':
            return DateSearchCriteria(key.filter_datetime, '=', params)
        elif key.value == b'SINCE':
            return DateSearchCriteria(key.filter_datetime, '>', params)
        elif key.value == b'SENTBEFORE':
            return HeaderDateSearchCriteria(key.filter_datetime, '<', params)
        elif key.value == b'SENTON':
            return HeaderDateSearchCriteria(key.filter_datetime, '=', params)
        elif key.value == b'SENTSINCE':
            return HeaderDateSearchCriteria(key.filter_datetime, '>', params)
        elif key.value == b'SMALLER':
            return SizeSearchCriteria(key.filter_int, '<', params)
        elif key.value == b'LARGER':
            return SizeSearchCriteria(key.filter_int, '>', params)
        elif key.value in (b'BCC', b'CC', b'FROM', b'SUBJECT', b'TO'):
            return EnvelopeSearchCriteria(key.value, key.filter_str, params)
        elif key.value == b'HEADER':
            name, value = key.filter_header
            return HeaderSearchCriteria(name, value, params)
        elif key.value in (b'BODY', b'TEXT'):
            value = key.filter_str
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

    def matches(self, msg_seq: int, msg: MessageInterface) -> bool:
        """The message matches if all the defined search key criteria match.

        Args:
            msg_seq: The message sequence ID.
            msg: The message object.

        """
        return all(crit.matches(msg_seq, msg) for crit in self.all_criteria)


class InverseSearchCriteria(SearchCriteria):
    """Matches only if the given search criteria does not match."""

    def __init__(self, key: SearchKey, params: SearchParams) -> None:
        super().__init__(params)
        self.key = SearchCriteria.of(key, params)

    def matches(self, msg_seq: int, msg: MessageInterface) -> bool:
        return not self.key.matches(msg_seq, msg)


class AllSearchCriteria(SearchCriteria):
    """Always matches anything."""

    def matches(self, msg_seq: int, msg: MessageInterface):
        return True


class OrSearchCriteria(SearchCriteria):
    """Matches if either of the search criteria match."""

    def __init__(self, left: SearchKey, right: SearchKey,
                 params: SearchParams) -> None:
        super().__init__(params)
        self.left = SearchCriteria.of(left, self.params)
        self.right = SearchCriteria.of(right, self.params)

    def matches(self, msg_seq: int, msg: MessageInterface) -> bool:
        return (self.left.matches(msg_seq, msg)
                or self.right.matches(msg_seq, msg))


class SequenceSetSearchCriteria(SearchCriteria):
    """Matches if the message is contained in the sequence set."""

    def __init__(self, seq_set: SequenceSet, params: SearchParams) -> None:
        super().__init__(params)
        self.seq_set = seq_set

    def matches(self, msg_seq: int, msg: MessageInterface) -> bool:
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

    def matches(self, msg_seq: int, msg: MessageInterface) -> bool:
        has_flag = self.flag in msg.get_flags(self.params.session_flags)
        expected = self.expected
        return (has_flag and expected) or (not expected and not has_flag)


class NewSearchCriteria(SearchCriteria):
    """Matches if the message is considered "new", i.e. recent and unseen."""

    def matches(self, msg_seq: int, msg: MessageInterface) -> bool:
        flags = msg.get_flags(self.params.session_flags)
        return Recent in flags and Seen not in flags


class DateSearchCriteria(SearchCriteria):
    """Matches by comparing against the internal date of the message."""

    def __init__(self, when: datetime, cmp: str, params: SearchParams) -> None:
        super().__init__(params)
        self.when = when.date()
        self.cmp = cmp

    @classmethod
    def _get_msg_date(cls, msg: MessageInterface) -> Optional[datetime]:
        return msg.internal_date

    def matches(self, msg_seq: int, msg: MessageInterface) -> bool:
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
        raise ValueError(self.cmp)


class HeaderDateSearchCriteria(DateSearchCriteria):
    """Matches by comparing against the ``Date:`` header of the message."""

    @classmethod
    def _get_msg_date(cls, msg: MessageInterface) -> Optional[datetime]:
        envelope = msg.get_envelope_structure()
        return envelope.date.datetime if envelope.date else None


class SizeSearchCriteria(SearchCriteria):
    """Matches by comparing against the size of the message."""

    def __init__(self, size: int, cmp: str, params: SearchParams) -> None:
        super().__init__(params)
        self.size = size
        self.cmp = cmp

    def matches(self, msg_seq: int, msg: MessageInterface) -> bool:
        size = msg.get_size()
        if self.cmp == '<':
            return size < self.size
        elif self.cmp == '>':
            return size > self.size
        raise ValueError(self.cmp)


class EnvelopeSearchCriteria(SearchCriteria):
    """Matches by checking for strings within various fields of the envelope
    structure.

    """

    def __init__(self, key: bytes, value: str, params: SearchParams) -> None:
        super().__init__(params)
        self.key = key
        self.value = value

    def matches(self, msg_seq: int, msg: MessageInterface) -> bool:
        envelope = msg.get_envelope_structure()
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
        raise ValueError(self.key)


class HeaderSearchCriteria(SearchCriteria):
    """Matches if the message has a header containing a value."""

    def __init__(self, name: str, value: str, params: SearchParams) -> None:
        super().__init__(params)
        self.name = name
        self.value = value

    def matches(self, msg_seq: int, msg: MessageInterface) -> bool:
        values = msg.get_header(self.name)
        return any(self.value in str(value) for value in values)


class BodySearchCriteria(SearchCriteria):
    """Matches if the message body contains a value."""

    def __init__(self, value: str, with_headers: bool,
                 params: SearchParams) -> None:
        super().__init__(params)
        self.with_headers = with_headers
        self.value = bytes(value, 'utf-8', 'replace')

    def matches(self, msg_seq: int, msg: MessageInterface) -> bool:
        data = msg.get_body() if self.with_headers else msg.get_text()
        return data is not None and self.value in data
