from abc import abstractmethod
from datetime import datetime
from typing import Optional, Iterable, Set, FrozenSet, Sequence, TypeVar
from typing_extensions import Protocol

from ..flags import FlagOp, SessionFlags
from ..parsing.response.fetch import EnvelopeStructure, BodyStructure
from ..parsing.specials import Flag

__all__ = ['Header', 'MessageInterface', 'LoadedMessageInterface']

_MessageT = TypeVar('_MessageT', bound='MessageInterface')


class Header(Protocol):
    """A message header value, which is convertible to a string with
    :class:`str`.

    """

    @abstractmethod
    def __str__(self) -> str:
        ...


class MessageInterface(Protocol):
    """Message metadata such as UID, permanent flags, and when the message
    was added to the system.

    """

    @property
    @abstractmethod
    def uid(self) -> int:
        """The message's unique identifier in the mailbox."""
        ...

    @property
    @abstractmethod
    def permanent_flags(self) -> Set[Flag]:
        """The message's set of permanent flags."""
        ...

    @property
    @abstractmethod
    def internal_date(self) -> Optional[datetime]:
        """The message's internal date."""
        ...

    @abstractmethod
    def copy(self: _MessageT, new_uid: int) -> _MessageT:
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
    def update_flags(self, flag_set: Iterable[Flag],
                     flag_op: FlagOp = FlagOp.REPLACE) -> FrozenSet[Flag]:
        """Update the permanent flags for the message. Returns the resulting
        set of permanent flags.

        Args:
            flag_set: The set of flags for the update operation.
            flag_op: The mode to change the flags.

        """
        ...


class LoadedMessageInterface(MessageInterface):
    """A message with its contents loaded, such that it pulls the information
    from a message object necessary to gather `message attributes
    <https://tools.ietf.org/html/rfc3501#section-2.3>`_, as needed by the
    `FETCH responses <https://tools.ietf.org/html/rfc3501#section-7.4.2>`_.

    """

    @abstractmethod
    def get_header(self, name: bytes) -> Sequence[Header]:
        """Get the values of a header from the message.

        Args:
            name: The name of the header.

        """
        ...

    @abstractmethod
    def get_headers(self, section: Iterable[int] = None,
                    subset: Iterable[bytes] = None,
                    inverse: bool = False) -> Optional[bytes]:
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
                 binary: bool = False) -> Optional[bytes]:
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
                 binary: bool = False) -> Optional[bytes]:
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
