
from abc import abstractmethod
from datetime import datetime
from typing import TypeVar, Tuple, NamedTuple, Sequence, FrozenSet, Collection
from typing_extensions import Protocol

from ..bytes import Writeable
from ..flags import SessionFlags
from ..parsing.response.fetch import EnvelopeStructure, BodyStructure
from ..parsing.specials import Flag, ExtensionOptions

__all__ = ['AppendMessage', 'CachedMessage', 'MessageInterface', 'MessageT',
           'FlagsKey']

#: Type variable with an upper bound of :class:`MessageInterface`.
MessageT = TypeVar('MessageT', bound='MessageInterface')

#: Type alias for the value used as a key in set comparisons detecting flag
#: updates.
FlagsKey = Tuple[int, FrozenSet[Flag]]


class AppendMessage(NamedTuple):
    """A single message from the APPEND command.

    Args:
        message: The raw message bytes.
        flag_set: The flags to assign to the message.
        when: The internal timestamp to assign to the message.
        options: The extension options in use for the message.

    """

    message: bytes
    flag_set: FrozenSet[Flag]
    when: datetime
    options: ExtensionOptions


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
    def internal_date(self) -> datetime:
        """The message's internal date."""
        ...

    @property
    @abstractmethod
    def permanent_flags(self) -> FrozenSet[Flag]:
        """The permanent flags for the message."""
        ...

    @property
    @abstractmethod
    def flags_key(self) -> FlagsKey:
        """Hashable value that represents the current flags of this
        message, used for detecting mailbox updates.

        """
        ...

    @abstractmethod
    def get_flags(self, session_flags: SessionFlags) -> FrozenSet[Flag]:
        """Get the full set of permanent and session flags for the message.

        Args:
            session_flags: The current session flags.

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
    def permanent_flags(self) -> FrozenSet[Flag]:
        """The permanent flags for the message."""
        ...

    @property
    @abstractmethod
    def internal_date(self) -> datetime:
        """The message's internal date."""
        ...

    @property
    @abstractmethod
    def append_msg(self) -> AppendMessage:
        """A copy of the message for appending to a mailbox."""
        ...

    @abstractmethod
    def copy(self: MessageT, new_uid: int) -> MessageT:
        """Return a copy of the message with a new UID.

        Args:
            new_uid: The copied message UID.

        """
        ...

    @abstractmethod
    def get_flags(self, session_flags: SessionFlags) -> FrozenSet[Flag]:
        """Get the full set of permanent and session flags for the message.

        Args:
            session_flags: The current session flags.

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
    def get_headers(self, section: Sequence[int] = None,
                    subset: Collection[bytes] = None,
                    inverse: bool = False) -> Writeable:
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
    def get_body(self, section: Sequence[int] = None,
                 binary: bool = False) -> Writeable:
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
    def get_text(self, section: Sequence[int] = None,
                 binary: bool = False) -> Writeable:
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
    def get_size(self, section: Sequence[int] = None,
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
