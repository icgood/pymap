"""Utilities for managing IMAP searches."""

from __future__ import annotations

import re
from abc import abstractmethod, ABCMeta
from collections.abc import Iterable
from datetime import datetime
from typing import AnyStr, Optional, Final

from .exceptions import SearchNotAllowed
from .interfaces.message import MessageInterface, LoadedMessageInterface
from .parsing.specials import ObjectId, SearchKey, SequenceSet
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

    __slots__ = ['selected', 'disabled', 'max_seq', 'max_uid', 'session_flags']

    def __init__(self, selected: SelectedMailbox, *,
                 disabled: Iterable[bytes] = None) -> None:
        self.selected: Final = selected
        self.disabled: Final = frozenset(disabled or [])
        self.max_seq: Final = selected.messages.exists
        self.max_uid: Final = selected.messages.max_uid
        self.session_flags: Final = selected.session_flags


class SearchCriteria(metaclass=ABCMeta):
    """Base class for different types of search criteria.

    Args:
        params: The parameters that may be used by some searches.

    """

    def __init__(self, params: SearchParams) -> None:
        self.params = params

    @classmethod
    def _in(cls, substr: AnyStr, data: AnyStr) -> bool:
        re_flags = re.I | re.A
        escaped_substr = re.escape(substr)
        return re.search(escaped_substr, data, re_flags) is not None

    @abstractmethod
    def matches(self, msg_seq: int, msg: MessageInterface,
                loaded_msg: LoadedMessageInterface) -> bool:
        """Implemented by sub-classes to define the search criteria.

        Args:
            msg_seq: The message sequence ID.
            msg: The message object.
            loaded_msg: The message content.

        """
        ...

    @classmethod
    def of(cls, key: SearchKey, params: SearchParams) -> SearchCriteria:
        """Factory method for producing a search criteria sub-class from a
        search key.

        Args:
            key: The search key defining the criteria.
            params: The parameters that may be used by some searches.

        """
        key_name = key.value
        if key_name in params.disabled:
            raise SearchNotAllowed(key)
        elif key.inverse:
            return InverseSearchCriteria(key.not_inverse, params)
        elif key_name == b'SEQSET':
            return SequenceSetSearchCriteria(key.filter_sequence_set, params)
        elif key_name == b'KEYSET':
            return SearchCriteriaSet(key.filter_key_set, params)
        elif key_name == b'ALL':
            return AllSearchCriteria(params)
        elif key_name == b'OR':
            left_key, right_key = key.filter_key_or
            return OrSearchCriteria(left_key, right_key, params)
        elif key_name == b'EMAILID':
            return HasEmailIdSearchCriteria(key.filter_object_id, params)
        elif key_name == b'THREADID':
            return HasThreadIdSearchCriteria(key.filter_object_id, params)
        elif key_name == b'ANSWERED':
            return HasFlagSearchCriteria(Answered, True, params)
        elif key_name == b'UNANSWERED':
            return HasFlagSearchCriteria(Answered, False, params)
        elif key_name == b'DELETED':
            return HasFlagSearchCriteria(Deleted, True, params)
        elif key_name == b'UNDELETED':
            return HasFlagSearchCriteria(Deleted, False, params)
        elif key_name == b'DRAFT':
            return HasFlagSearchCriteria(Draft, True, params)
        elif key_name == b'UNDRAFT':
            return HasFlagSearchCriteria(Draft, False, params)
        elif key_name == b'FLAGGED':
            return HasFlagSearchCriteria(Flagged, True, params)
        elif key_name == b'UNFLAGGED':
            return HasFlagSearchCriteria(Flagged, False, params)
        elif key_name == b'RECENT':
            return HasFlagSearchCriteria(Recent, True, params)
        elif key_name == b'OLD':
            return HasFlagSearchCriteria(Recent, False, params)
        elif key_name == b'SEEN':
            return HasFlagSearchCriteria(Seen, True, params)
        elif key_name == b'UNSEEN':
            return HasFlagSearchCriteria(Seen, False, params)
        elif key_name == b'KEYWORD':
            return HasFlagSearchCriteria(key.filter_flag, True, params)
        elif key_name == b'UNKEYWORD':
            return HasFlagSearchCriteria(key.filter_flag, False, params)
        elif key_name == b'NEW':
            return NewSearchCriteria(params)
        elif key_name == b'BEFORE':
            return DateSearchCriteria(key.filter_datetime, '<', params)
        elif key_name == b'ON':
            return DateSearchCriteria(key.filter_datetime, '=', params)
        elif key_name == b'SINCE':
            return DateSearchCriteria(key.filter_datetime, '>=', params)
        elif key_name == b'SENTBEFORE':
            return HeaderDateSearchCriteria(key.filter_datetime, '<', params)
        elif key_name == b'SENTON':
            return HeaderDateSearchCriteria(key.filter_datetime, '=', params)
        elif key_name == b'SENTSINCE':
            return HeaderDateSearchCriteria(key.filter_datetime, '>=', params)
        elif key_name == b'SMALLER':
            return SizeSearchCriteria(key.filter_int, '<', params)
        elif key_name == b'LARGER':
            return SizeSearchCriteria(key.filter_int, '>', params)
        elif key_name in (b'BCC', b'CC', b'FROM', b'SUBJECT', b'TO'):
            return EnvelopeSearchCriteria(key_name, key.filter_str, params)
        elif key_name == b'HEADER':
            name, value = key.filter_header
            return HeaderSearchCriteria(name, value, params)
        elif key_name in (b'BODY', b'TEXT'):
            return BodySearchCriteria(key.filter_str, params)
        raise SearchNotAllowed(key)


class SearchCriteriaSet(SearchCriteria):
    """Search criteria composed of a set of search criteria that must all
    match. If the set is empty, nothing will match.

    Args:
        keys: The set of search keys that must match.
        params: The parameters that may be used by some searches.

    """

    def __init__(self, keys: frozenset[SearchKey],
                 params: SearchParams) -> None:
        super().__init__(params)
        self.all_criteria = [SearchCriteria.of(key, params) for key in keys]

    @property
    def sequence_set(self) -> SequenceSet:
        """The sequence set to use when finding the messages to match against.
        This will default to all messages unless the search criteria set
        contains a sequence set.

        """
        try:
            seqset_crit = next(crit for crit in self.all_criteria
                               if isinstance(crit, SequenceSetSearchCriteria))
        except StopIteration:
            return SequenceSet.all()
        else:
            return seqset_crit.seq_set

    def matches(self, msg_seq: int, msg: MessageInterface,
                loaded_msg: LoadedMessageInterface) -> bool:
        """The message matches if all the defined search key criteria match.

        Args:
            msg_seq: The message sequence ID.
            msg: The message object.

        """
        return all(crit.matches(msg_seq, msg, loaded_msg)
                   for crit in self.all_criteria)


class InverseSearchCriteria(SearchCriteria):
    """Matches only if the given search criteria does not match."""

    def __init__(self, key: SearchKey, params: SearchParams) -> None:
        super().__init__(params)
        self.key = SearchCriteria.of(key, params)

    def matches(self, msg_seq: int, msg: MessageInterface,
                loaded_msg: LoadedMessageInterface) -> bool:
        return not self.key.matches(msg_seq, msg, loaded_msg)


class AllSearchCriteria(SearchCriteria):
    """Always matches anything."""

    def matches(self, msg_seq: int, msg: MessageInterface,
                loaded_msg: LoadedMessageInterface) -> bool:
        return True


class OrSearchCriteria(SearchCriteria):
    """Matches if either of the search criteria match."""

    def __init__(self, left: SearchKey, right: SearchKey,
                 params: SearchParams) -> None:
        super().__init__(params)
        self.left = SearchCriteria.of(left, self.params)
        self.right = SearchCriteria.of(right, self.params)

    def matches(self, msg_seq: int, msg: MessageInterface,
                loaded_msg: LoadedMessageInterface) -> bool:
        return (self.left.matches(msg_seq, msg, loaded_msg)
                or self.right.matches(msg_seq, msg, loaded_msg))


class SequenceSetSearchCriteria(SearchCriteria):
    """Matches if the message is contained in the sequence set."""

    def __init__(self, seq_set: SequenceSet, params: SearchParams) -> None:
        super().__init__(params)
        self.seq_set = seq_set
        if seq_set.uid:
            self.flat = seq_set.flatten(params.max_uid)
        else:
            self.flat = seq_set.flatten(params.max_seq)

    def matches(self, msg_seq: int, msg: MessageInterface,
                loaded_msg: LoadedMessageInterface) -> bool:
        if self.seq_set.uid:
            return msg.uid in self.flat
        else:
            return msg_seq in self.flat


class HasEmailIdSearchCriteria(SearchCriteria):
    """Matches if the message has the same
    :attr:`~pymap.interfaces.message.MessageInterface.email_id` value.

    """

    def __init__(self, email_id: ObjectId, params: SearchParams) -> None:
        super().__init__(params)
        self.email_id = email_id

    def matches(self, msg_seq: int, msg: MessageInterface,
                loaded_msg: LoadedMessageInterface) -> bool:
        try:
            email_id = msg.email_id
        except ValueError:
            return False
        else:
            return self.email_id == email_id


class HasThreadIdSearchCriteria(SearchCriteria):
    """Matches if the message has the same
    :attr:`~pymap.interfaces.message.MessageInterface.thread_id` value.

    """

    def __init__(self, thread_id: ObjectId, params: SearchParams) -> None:
        super().__init__(params)
        self.thread_id = thread_id

    def matches(self, msg_seq: int, msg: MessageInterface,
                loaded_msg: LoadedMessageInterface) -> bool:
        return self.thread_id == msg.thread_id


class HasFlagSearchCriteria(SearchCriteria):
    """Matches if the message has the given flag in their permanent or
    session flag sets.

    """

    def __init__(self, flag: Flag, expected: bool,
                 params: SearchParams) -> None:
        super().__init__(params)
        self.flag = flag
        self.expected = expected

    def matches(self, msg_seq: int, msg: MessageInterface,
                loaded_msg: LoadedMessageInterface) -> bool:
        has_flag = self.flag in msg.get_flags(self.params.session_flags)
        expected = self.expected
        return (has_flag and expected) or (not expected and not has_flag)


class NewSearchCriteria(SearchCriteria):
    """Matches if the message is considered "new", i.e. recent and unseen."""

    def matches(self, msg_seq: int, msg: MessageInterface,
                loaded_msg: LoadedMessageInterface) -> bool:
        flags = msg.get_flags(self.params.session_flags)
        return Recent in flags and Seen not in flags


class DateSearchCriteria(SearchCriteria):
    """Matches by comparing against the internal date of the message."""

    def __init__(self, when: datetime, op: str, params: SearchParams) -> None:
        super().__init__(params)
        self.when = when.date()
        self.op = op

    @classmethod
    def _get_msg_date(cls, msg: MessageInterface,
                      loaded_msg: LoadedMessageInterface) \
            -> Optional[datetime]:
        return msg.internal_date

    def matches(self, msg_seq: int, msg: MessageInterface,
                loaded_msg: LoadedMessageInterface) -> bool:
        msg_datetime = self._get_msg_date(msg, loaded_msg)
        if msg_datetime is None:
            return False
        msg_date = msg_datetime.date()
        if self.op == '<':  # BEFORE
            return msg_date < self.when
        elif self.op == '=':  # ON
            return msg_date == self.when
        elif self.op == '>=':  # SINCE
            return msg_date >= self.when
        raise ValueError(self.op)


class HeaderDateSearchCriteria(DateSearchCriteria):
    """Matches by comparing against the ``Date:`` header of the message."""

    @classmethod
    def _get_msg_date(cls, msg: MessageInterface,
                      loaded_msg: LoadedMessageInterface) \
            -> Optional[datetime]:
        envelope = loaded_msg.get_envelope_structure()
        return envelope.date.datetime if envelope.date else None


class SizeSearchCriteria(SearchCriteria):
    """Matches by comparing against the size of the message."""

    def __init__(self, size: int, op: str, params: SearchParams) -> None:
        super().__init__(params)
        self.size = size
        self.op = op

    def matches(self, msg_seq: int, msg: MessageInterface,
                loaded_msg: LoadedMessageInterface) -> bool:
        size = loaded_msg.get_size()
        if self.op == '<':
            return size < self.size
        elif self.op == '>':
            return size > self.size
        raise ValueError(self.op)


class EnvelopeSearchCriteria(SearchCriteria):
    """Matches by checking for strings within various fields of the envelope
    structure.

    """

    def __init__(self, key: bytes, value: str, params: SearchParams) -> None:
        super().__init__(params)
        self.key = key
        self.value = value

    def matches(self, msg_seq: int, msg: MessageInterface,
                loaded_msg: LoadedMessageInterface) -> bool:
        envelope = loaded_msg.get_envelope_structure()
        if self.key == b'BCC':
            if not envelope.bcc:
                return False
            return any(self._in(self.value, str(bcc)) for bcc in envelope.bcc)
        elif self.key == b'CC':
            if not envelope.cc:
                return False
            return any(self._in(self.value, str(cc)) for cc in envelope.cc)
        elif self.key == b'FROM':
            if not envelope.from_:
                return False
            return any(self._in(self.value, str(from_))
                       for from_ in envelope.from_)
        elif self.key == b'SUBJECT':
            if not envelope.subject:
                return False
            return self._in(self.value, str(envelope.subject))
        elif self.key == b'TO':
            if not envelope.to:
                return False
            return any(self._in(self.value, str(to)) for to in envelope.to)
        raise ValueError(self.key)


class HeaderSearchCriteria(SearchCriteria):
    """Matches if the message has a header containing a value."""

    def __init__(self, name: str, value: str, params: SearchParams) -> None:
        super().__init__(params)
        self.name = name.encode('ascii')
        self.value = value

    def matches(self, msg_seq: int, msg: MessageInterface,
                loaded_msg: LoadedMessageInterface) -> bool:
        values = loaded_msg.get_header(self.name)
        return any(self._in(self.value, value) for value in values)


class BodySearchCriteria(SearchCriteria):
    """Matches if the message body contains a value."""

    def __init__(self, value: str, params: SearchParams) -> None:
        super().__init__(params)
        self.value = bytes(value, 'utf-8', 'replace')

    def matches(self, msg_seq: int, msg: MessageInterface,
                loaded_msg: LoadedMessageInterface) -> bool:
        return loaded_msg.contains(self.value)
