
from __future__ import annotations

import re
from typing import Optional, Sequence, List, Match, Pattern, Iterable, Iterator
from typing_extensions import Final

from .mime import MessageHeader

__all__ = ['ThreadKey']


class ThreadKey(Iterable[bytes]):
    """Represents a hashable key used to link messages as members of the same
    thread.

    The thread key is composed of a single message ID from the ``Message-Id``,
    ``In-Reply-To``, or ``References`` headers, along with a normalized version
    of the ``Subject`` header. If two messages share a single thread key, they
    should be assigned the same
    :attr:`~pymap.interfaces.message.MessageInterface.thread_id`.

    Args:
        msg_id: The message ID bytestring.
        subject: The normalized subject bytestring.

    """

    _pattern = re.compile(r'<[^>]*>')
    _whitespace = re.compile(r'\s+')
    _fwd_pattern = re.compile(r'\s*fwd\s*:\s*', re.I)
    _re_pattern = re.compile(r'\s*re\s*:\s*', re.I)
    _listtag_pattern = re.compile(r'\s*\[.*?\]\s*')

    __slots__ = ['msg_id', 'subject', '_pair', '__weakref__']

    def __init__(self, msg_id: bytes, subject: bytes) -> None:
        super().__init__()
        self.msg_id: Final = msg_id
        self.subject: Final = subject
        self._pair: Final = (msg_id, subject)

    def __eq__(self, other) -> bool:
        if isinstance(other, ThreadKey):
            return self._pair == other._pair
        return super().__eq__(other)

    def __hash__(self) -> int:
        return hash(self._pair)

    def __iter__(self) -> Iterator[bytes]:
        return iter(self._pair)

    @classmethod
    def _encode(cls, value: str) -> bytes:
        no_whitespace = cls._whitespace.sub('', value)
        return no_whitespace.encode('ascii', 'surrogateescape')

    @classmethod
    def _first_match(cls, value: str, *patterns: Pattern[str]) \
            -> Optional[Match[str]]:
        for pattern in patterns:
            match = pattern.match(value)
            if match is not None:
                return match
        return None

    @classmethod
    def _subject(cls, value: str) -> bytes:
        match = cls._first_match(
            value, cls._fwd_pattern, cls._re_pattern, cls._listtag_pattern)
        if match is None:
            value = cls._whitespace.sub(' ', value.strip())
            return value.encode('ascii', 'surrogateescape')
        else:
            return cls._subject(value[match.end(0):])

    @classmethod
    def get_all(cls, header: MessageHeader) -> Sequence[ThreadKey]:
        """Return all the thread keys from the message headers.

        Args:
            header: The message header.

        """
        ret: List[ThreadKey] = []
        message_id = header.parsed.message_id
        in_reply_to = header.parsed.in_reply_to
        references = header.parsed.references
        subject = header.parsed.subject
        subject_key = cls._subject(str(subject)) if subject else b''
        if message_id is not None:
            match = cls._pattern.search(str(message_id))
            if match is not None:
                ret.append(cls(cls._encode(match.group(0)), subject_key))
        if in_reply_to is not None:
            for match in cls._pattern.finditer(str(in_reply_to)):
                ret.append(cls(cls._encode(match.group(0)), subject_key))
        if references is not None:
            for match in cls._pattern.finditer(str(references)):
                ret.append(cls(cls._encode(match.group(0)), subject_key))
        return ret
