
from abc import abstractmethod
from datetime import datetime
from typing import TypeVar, Optional, Iterable, Tuple, Sequence, \
    FrozenSet, AbstractSet
from typing_extensions import Protocol

from ..flags import FlagOp, SessionFlags
from ..parsing.response.fetch import EnvelopeStructure, BodyStructure
from ..parsing.specials import Flag

__all__ = ['CachedMessage', 'MessageInterface', 'MessageT']

#: Type variable with an upper bound of :class:`MessageInterface`.
MessageT = TypeVar('MessageT', bound='MessageInterface')


class CachedMessage(Protocol):
    """Cached message metadata used to track state changes. Used to produce
    untagged FETCH responses when a message's flags have changed, or when a
    FETCH command requests metadata of an expunged message before its untagged
    EXPUNGE response has been sent.

    This is intended to be compatible with :class:`MessageInterface`, and
    should be implemented by the same classes in most cases.

    """

    @property
    @abstractmethod
    def uid(self) -> int:
        """The message's unique identifier in the mailbox."""
        ...

    @property
    @abstractmethod
    def internal_date(self) -> Optional[datetime]:
        """The message's internal date."""
        ...

    @abstractmethod
    def get_flags(self, session_flags: SessionFlags = None) -> FrozenSet[Flag]:
        """Get the full set of permanent and session flags for the message. If
        ``session_flags`` is not given, only permanent flags are returned.

        Args:
            session_flags: The current session flags.

        """
        ...

    @property
    @abstractmethod
    def flags_key(self) -> Tuple[int, FrozenSet[Flag]]:
        """Hashable value that represents the current flags of this
        message, used for detecting mailbox updates.

        """
        ...


class MessageInterface(Protocol):
    """Message data including content and metadata such as UID, permanent
    flags, and when the message was added to the system.

    """

    @property
    @abstractmethod
    def uid(self) -> int:
        """The message's unique identifier in the mailbox."""
        ...

    @property
    @abstractmethod
    def expunged(self) -> bool:
        """True if this message has been expunged from the mailbox."""
        ...

    @property
    @abstractmethod
    def internal_date(self) -> Optional[datetime]:
        """The message's internal date."""
        ...

    @abstractmethod
    def copy(self: MessageT, new_uid: int) -> MessageT:
        """Return a copy of the message with a new UID.

        Args:
            new_uid: The copied message UID.

        """
        ...

    @abstractmethod
    def get_flags(self, session_flags: SessionFlags = None) -> FrozenSet[Flag]:
        """Get the full set of permanent and session flags for the message.

        Args:
            session_flags: The current session flags.

        """
        ...

    @abstractmethod
    def update_flags(self, flag_set: AbstractSet[Flag],
                     flag_op: FlagOp = FlagOp.REPLACE) -> None:
        """Update the permanent flags for the message.

        Args:
            flag_set: The set of flags for the update operation.
            flag_op: The mode to change the flags.

        """
        ...

    @abstractmethod
    def get_header(self, name: bytes) -> Sequence[str]:
        """Get the values of a header from the message.

        Args:
            name: The name of the header.

        """
        ...

    @abstractmethod
    def get_headers(self, section: Iterable[int] = None,
                    subset: Iterable[bytes] = None,
                    inverse: bool = False) -> bytes:
        """Get the headers from the message.

        The ``section`` argument can index a nested sub-part of the message.
        For example, ``[2, 3]`` would get the 2nd sub-part of the message and
        then index it for its 3rd sub-part.

        Args:
            section: Optional nested list of sub-part indexes.
            subset: Subset of headers to get.
            inverse: If ``subset`` is given, this flag will invert it so that
                the headers *not* in ``subset`` are returned.

        """
        ...

    @abstractmethod
    def get_body(self, section: Iterable[int] = None,
                 binary: bool = False) -> bytes:
        """Get the full body of the message part, including headers.

        The ``section`` argument can index a nested sub-part of the message.
        For example, ``[2, 3]`` would get the 2nd sub-part of the message and
        then index it for its 3rd sub-part.

        Args:
            section: Optional nested list of sub-part indexes.
            binary: True if the result uses 8-bit encoding.

        """
        ...

    @abstractmethod
    def get_text(self, section: Iterable[int] = None,
                 binary: bool = False) -> bytes:
        """Get the text of the message part, not including headers.

        The ``section`` argument can index a nested sub-part of the message.
        For example, ``[2, 3]`` would get the 2nd sub-part of the message and
        then index it for its 3rd sub-part.

        Args:
            section: Optional nested list of sub-part indexes.
            binary: True if the result uses 8-bit encoding.

        """
        ...

    @abstractmethod
    def get_size(self, section: Iterable[int] = None,
                 binary: bool = False) -> int:
        """Return the size of the message, in octets.

        Args:
            section: Optional nested list of sub-part indexes.
            binary: True if the result uses 8-bit encoding.

        """
        ...

    @abstractmethod
    def get_envelope_structure(self) -> EnvelopeStructure:
        """Build and return the envelope structure.

        See Also:
            `RFC 3501 2.3.5.
            <https://tools.ietf.org/html/rfc3501#section-2.3.5>`_

        """
        ...

    @abstractmethod
    def get_body_structure(self) -> BodyStructure:
        """Build and return the body structure.

        See Also:
            `RFC 3501 2.3.6
            <https://tools.ietf.org/html/rfc3501#section-2.3.6>`_

        """
        ...

    @abstractmethod
    def contains(self, value: bytes) -> bool:
        """Check the body of the message for a sub-string. This may be
        optimized to only search headers and ``text/*`` MIME parts.

        Args:
            value: The sub-string to find.

        """
        ...
