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

from datetime import datetime
from typing import cast, FrozenSet, Tuple, Optional, Iterable

from .exceptions import SearchNotAllowed
from .interfaces.message import Message, LoadedMessage
from .mailbox import MailboxSession
from .parsing.specials import SearchKey, SequenceSet
from .parsing.specials.flag import Flag, Keyword, Answered, Deleted, Draft, \
    Flagged, Recent, Seen

__all__ = ['SearchParams', 'SearchCriteria', 'SearchCriteriaSet']


class SearchParams:
    """Defines certain parameters and routines necessary to process any
    kind of search criteria. If a parameter is not supplied, or a method not
    implemented, any search keys that require it will fail.

    :param session: The active mailbox session.
    :param max_seq: The highest message sequence ID in the mailbox.
    :param max_uid: The highest message UID in the mailbox.
    :param disabled: Search keys that should be disabled.

    """

    def __init__(self, session: MailboxSession,
                 max_seq: int = None, max_uid: int = None,
                 disabled: Iterable[bytes] = None) -> None:
        self.session = session
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

    def __init__(self, params: SearchParams, inverse: bool) -> None:
        self.params = params
        self.inverse = inverse

    def _matches(self, msg_seq: int, msg: Message) -> bool:
        raise NotImplementedError

    def matches(self, msg_seq: int, msg: Message) -> bool:
        matches = self._matches(msg_seq, msg)
        inverse = self.inverse
        return (matches and not inverse) or (not matches and inverse)

    @classmethod
    def of(cls, key: SearchKey, params: SearchParams) -> 'SearchCriteria':
        args = (params, key.inverse)
        args_inverse = (params, not key.inverse)
        if key.value in params.disabled:
            raise SearchNotAllowed(key.value)
        elif key.value == b'SEQSET' and isinstance(key.filter, SequenceSet):
            return SequenceSetSearchCriteria(key.filter, *args)
        elif key.value == b'KEYSET' and isinstance(key.filter, frozenset):
            keys = cast(FrozenSet[SearchKey], key.filter)
            return SearchCriteriaSet(keys, *args)
        elif key.value == b'ALL':
            return AllSearchCriteria(*args)
        elif key.value == b'OR':
            keys = cast(Tuple[SearchKey, SearchKey], key.filter)
            return OrSearchCriteria(keys[0], keys[1], *args)
        elif key.value == b'ANSWERED':
            return HasFlagSearchCriteria(Answered, *args)
        elif key.value == b'UNANSWERED':
            return HasFlagSearchCriteria(Answered, params, *args_inverse)
        elif key.value == b'DELETED':
            return HasFlagSearchCriteria(Deleted, *args)
        elif key.value == b'UNDELETED':
            return HasFlagSearchCriteria(Deleted, *args_inverse)
        elif key.value == b'DRAFT':
            return HasFlagSearchCriteria(Draft, *args)
        elif key.value == b'UNDRAFT':
            return HasFlagSearchCriteria(Draft, *args_inverse)
        elif key.value == b'FLAGGED':
            return HasFlagSearchCriteria(Flagged, *args)
        elif key.value == b'UNFLAGGED':
            return HasFlagSearchCriteria(Flagged, *args_inverse)
        elif key.value == b'RECENT':
            return HasFlagSearchCriteria(Recent, *args)
        elif key.value == b'OLD':
            return HasFlagSearchCriteria(Recent, *args_inverse)
        elif key.value == b'SEEN':
            return HasFlagSearchCriteria(Seen, *args)
        elif key.value == b'UNSEEN':
            return HasFlagSearchCriteria(Seen, *args_inverse)
        elif key.value == b'KEYWORD':
            keyword = cast(Keyword, key.filter)
            return HasFlagSearchCriteria(keyword, *args)
        elif key.value == b'UNKEYWORD':
            keyword = cast(Keyword, key.filter)
            return HasFlagSearchCriteria(keyword, *args_inverse)
        elif key.value == b'NEW':
            return NewSearchCriteria(*args)
        elif key.value == b'BEFORE':
            when = cast(datetime, key.filter)
            return DateSearchCriteria(when, '<', *args)
        elif key.value == b'ON':
            when = cast(datetime, key.filter)
            return DateSearchCriteria(when, '=', *args)
        elif key.value == b'SINCE':
            when = cast(datetime, key.filter)
            return DateSearchCriteria(when, '>', *args)
        elif key.value == b'SENTBEFORE':
            when = cast(datetime, key.filter)
            return HeaderDateSearchCriteria(when, '<', *args)
        elif key.value == b'SENTON':
            when = cast(datetime, key.filter)
            return HeaderDateSearchCriteria(when, '=', *args)
        elif key.value == b'SENTSINCE':
            when = cast(datetime, key.filter)
            return HeaderDateSearchCriteria(when, '>', *args)
        elif key.value == b'SMALLER':
            size = cast(int, key.filter)
            return SizeSearchCriteria(size, '<', *args)
        elif key.value == b'LARGER':
            size = cast(int, key.filter)
            return SizeSearchCriteria(size, '>', *args)
        elif key.value in (b'BCC', b'CC', b'FROM', b'SUBJECT', b'TO'):
            value = cast(str, key.filter)
            return EnvelopeSearchCriteria(key.value, value, *args)
        elif key.value == b'HEADER':
            name, value = cast(Tuple[str, str], key.filter)
            return HeaderSearchCriteria(name, value, *args)
        elif key.value in (b'BODY', b'TEXT'):
            value = cast(str, key.filter)
            return BodySearchCriteria(value, key.value == b'TEXT', *args)
        raise SearchNotAllowed(key.value)


class LoadedSearchCriteria(SearchCriteria):

    def _matches(self, msg_seq: int, msg: Message) -> bool:
        raise NotImplementedError

    def matches(self, msg_seq: int, msg: Message) -> bool:
        if isinstance(msg, LoadedMessage):
            return super().matches(msg_seq, msg)
        else:
            raise SearchNotAllowed


class SearchCriteriaSet(SearchCriteria):

    def __init__(self, keys: FrozenSet[SearchKey], params: SearchParams,
                 inverse: bool = False) -> None:
        super().__init__(params, inverse)
        self.all_criteria = [SearchCriteria.of(key, params) for key in keys]

    def _matches(self, msg_seq: int, msg: Message) -> bool:
        return all(crit.matches(msg_seq, msg) for crit in self.all_criteria)


class AllSearchCriteria(SearchCriteria):

    def _matches(self, msg_seq: int, msg: Message):
        return True


class OrSearchCriteria(SearchCriteria):

    def __init__(self, left: SearchKey, right: SearchKey, *args) -> None:
        super().__init__(*args)
        self.left = SearchCriteria.of(left, self.params)
        self.right = SearchCriteria.of(right, self.params)

    def _matches(self, msg_seq: int, msg: Message) -> bool:
        return (self.left.matches(msg_seq, msg)
                or self.right.matches(msg_seq, msg))


class SequenceSetSearchCriteria(SearchCriteria):

    def __init__(self, seq_set: SequenceSet, *args) -> None:
        super().__init__(*args)
        self.seq_set = seq_set

    def _matches(self, msg_seq: int, msg: Message) -> bool:
        if self.seq_set.uid:
            return self.seq_set.contains(msg.uid, self.params.max_uid)
        else:
            return self.seq_set.contains(msg_seq, self.params.max_seq)


class HasFlagSearchCriteria(SearchCriteria):

    def __init__(self, flag: Flag, *args) -> None:
        super().__init__(*args)
        self.flag = flag

    def _matches(self, msg_seq: int, msg: Message) -> bool:
        return self.flag in msg.get_flags(self.params.session)


class NewSearchCriteria(SearchCriteria):

    def _matches(self, msg_seq: int, msg: Message) -> bool:
        flags = msg.get_flags(self.params.session)
        return Recent in flags and Seen not in flags


class DateSearchCriteria(SearchCriteria):

    def __init__(self, when: datetime, cmp: str, *args) -> None:
        super().__init__(*args)
        self.when = when.date()
        self.cmp = cmp

    @classmethod
    def _get_msg_date(cls, msg: Message) -> Optional[datetime]:
        return msg.internal_date

    def _matches(self, msg_seq: int, msg: Message) -> bool:
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


class HeaderDateSearchCriteria(DateSearchCriteria, LoadedSearchCriteria):

    @classmethod
    def _get_msg_date(cls, msg: Message) -> Optional[datetime]:
        loaded = cast(LoadedMessage, msg)
        envelope = loaded.get_envelope_structure()
        return envelope.date.datetime if envelope.date else None


class SizeSearchCriteria(LoadedSearchCriteria):

    def __init__(self, size: int, cmp: str, *args) -> None:
        super().__init__(*args)
        self.size = size
        self.cmp = cmp

    def _matches(self, msg_seq: int, msg: Message) -> bool:
        loaded = cast(LoadedMessage, msg)
        size = loaded.get_size()
        if self.cmp == '<':
            return size < self.size
        elif self.cmp == '>':
            return size > self.size
        raise RuntimeError  # should not happen


class EnvelopeSearchCriteria(LoadedSearchCriteria):

    def __init__(self, key: bytes, value: str, *args) -> None:
        super().__init__(*args)
        self.key = key
        self.value = value

    def _matches(self, msg_seq: int, msg: Message) -> bool:
        loaded = cast(LoadedMessage, msg)
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


class HeaderSearchCriteria(LoadedSearchCriteria):

    def __init__(self, name: str, value: str, *args) -> None:
        super().__init__(*args)
        self.name = bytes(name, 'ascii', 'ignore')
        self.value = value

    def _matches(self, msg_seq: int, msg: Message) -> bool:
        loaded = cast(LoadedMessage, msg)
        values = loaded.get_header(self.name)
        return any(self.value in str(value) for value in values)


class BodySearchCriteria(LoadedSearchCriteria):

    def __init__(self, value: str, with_headers: bool, *args) -> None:
        super().__init__(*args)
        self.with_headers = with_headers
        self.value = bytes(value, 'utf-8')

    def _matches(self, msg_seq: int, msg: Message) -> bool:
        loaded = cast(LoadedMessage, msg)
        data = loaded.get_body() if self.with_headers else loaded.get_text()
        return data is not None and self.value in data
