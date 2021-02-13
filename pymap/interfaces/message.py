
from __future__ import annotations

from abc import abstractmethod
from collections.abc import Collection, Sequence
from datetime import datetime
from typing import TypeVar, Protocol

from ..bytes import Writeable
from ..flags import SessionFlags
from ..parsing.response.fetch import EnvelopeStructure, BodyStructure
from ..parsing.specials import Flag, ObjectId, FetchRequirement

__all__ = ['MessageT', 'MessageT_co', 'FlagsKey', 'CachedMessage',
           'MessageInterface', 'LoadedMessageInterface']

#: Type variable with an upper bound of :class:`MessageInterface`.
MessageT = TypeVar('MessageT', bound='MessageInterface')

#: Covariant type variable with an upper bound of :class:`MessageInterface`.
MessageT_co = TypeVar('MessageT_co', bound='MessageInterface', covariant=True)

#: Type alias for the value used as a key in set comparisons detecting flag
#: updates.
FlagsKey = tuple[int, frozenset[Flag]]


class CachedMessage(Protocol):
    """Cached message metadata used to track state changes. Used to produce
    untagged FETCH responses when a message's flags have changed, or when a
    FETCH command requests metadata of an expunged message before its untagged
    EXPUNGE response has been sent.

    This is intended to be compatible with :class:`MessageInterface`, and
    should be implemented by the same classes in most cases.

    """

    __slots__: Sequence[str] = []

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
    def permanent_flags(self) -> frozenset[Flag]:
        """The permanent flags for the message."""
        ...

    @property
    @abstractmethod
    def email_id(self) -> ObjectId:
        """The message's email object ID."""
        ...

    @property
    @abstractmethod
    def thread_id(self) -> ObjectId:
        """The message's thread object ID."""
        ...

    @property
    @abstractmethod
    def flags_key(self) -> FlagsKey:
        """Hashable value that represents the current flags of this
        message, used for detecting mailbox updates.

        """
        ...

    @abstractmethod
    def get_flags(self, session_flags: SessionFlags) -> frozenset[Flag]:
        """Get the full set of permanent and session flags for the message.

        Args:
            session_flags: The current session flags.

        """
        ...


class MessageInterface(Protocol):
    """Message data such as UID, permanent flags, and when the message was
    added to the system.

    """

    __slots__: Sequence[str] = []

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
    def internal_date(self) -> datetime:
        """The message's internal date."""
        ...

    @property
    @abstractmethod
    def permanent_flags(self) -> frozenset[Flag]:
        """The permanent flags for the message."""
        ...

    @property
    @abstractmethod
    def email_id(self) -> ObjectId:
        """The message's email object ID, which can identify its content.

        See Also:
            `RFC 8474 5.1. <https://tools.ietf.org/html/rfc8474#section-5.1>`_

        """
        ...

    @property
    @abstractmethod
    def thread_id(self) -> ObjectId:
        """The message's thread object ID, which groups messages together.

        See Also:
            `RFC 8474 5.2. <https://tools.ietf.org/html/rfc8474#section-5.2>`_

        """
        ...

    @abstractmethod
    def get_flags(self, session_flags: SessionFlags) -> frozenset[Flag]:
        """Get the full set of permanent and session flags for the message.

        Args:
            session_flags: The current session flags.

        """
        ...

    @abstractmethod
    async def load_content(self, requirement: FetchRequirement) \
            -> LoadedMessageInterface:
        """Loads the content of the message.

        Args:
            requirement: The data required from the message content.

        """
        ...


class LoadedMessageInterface(Protocol):
    """The loaded message content, which may include the header, the body,
    both, or neither, depending on the requirements.

    It is assumed that this object contains the entire content in-memory. As
    such, when multiple :class:`MessageInterface` objects are being processed,
    only one :class:`LoadedMessageInterface` should be in scope at a time.

    """

    __slots__: Sequence[str] = []

    @property
    @abstractmethod
    def requirement(self) -> FetchRequirement:
        """The :class:`~pymap.parsing.specials.FetchRequirement` used to load
        the message content.

        """
        ...

    @abstractmethod
    def __bytes__(self) -> bytes:
        ...

    @abstractmethod
    def get_header(self, name: bytes) -> Sequence[str]:
        """Get the values of a header from the message.

        Args:
            name: The name of the header.

        """
        ...

    @abstractmethod
    def get_headers(self, section: Sequence[int]) -> Writeable:
        """Get the headers from the message part.

        The ``section`` argument indexes a nested sub-part of the message. For
        example, ``[2, 3]`` would get the 2nd sub-part of the message and then
        index it for its 3rd sub-part.

        Args:
            section: Nested list of sub-part indexes.

        """
        ...

    @abstractmethod
    def get_message_headers(self, section: Sequence[int] = None,
                            subset: Collection[bytes] = None,
                            inverse: bool = False) -> Writeable:
        """Get the headers from the message or a ``message/rfc822`` sub-part of
        the message..

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
    def get_message_text(self, section: Sequence[int] = None) -> Writeable:
        """Get the text of the message part, not including headers.

        The ``section`` argument can index a nested sub-part of the message.
        For example, ``[2, 3]`` would get the 2nd sub-part of the message and
        then index it for its 3rd sub-part.

        Args:
            section: Optional nested list of sub-part indexes.

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
            binary: True if the result has decoded any
                Content-Transfer-Encoding.

        """
        ...

    @abstractmethod
    def get_size(self, section: Sequence[int] = None) -> int:
        """Return the size of the message, in octets.

        Args:
            section: Optional nested list of sub-part indexes.

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
