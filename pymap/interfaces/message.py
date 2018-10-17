from datetime import datetime
from email.headerregistry import BaseHeader
from typing import TYPE_CHECKING, Optional, Iterable, Set, FrozenSet, \
    Sequence, Union

from ..parsing.response.fetch import EnvelopeStructure, BodyStructure
from ..parsing.specials import Flag

__all__ = ['Message', 'LoadedMessage']

if TYPE_CHECKING:
    from ..mailbox import MailboxSession


class Message:
    """Message metadata such as UID, permanent flags, and when the message
    was added to the system.

    """

    @property
    def uid(self) -> int:
        """The message's unique identifier in the mailbox."""
        raise NotImplementedError

    @property
    def permanent_flags(self) -> Set[Flag]:
        """The message's set of permanent flags."""
        raise NotImplementedError

    @property
    def internal_date(self) -> Optional[datetime]:
        """The message's internal date."""
        raise NotImplementedError

    def get_flags(self, session: Optional['MailboxSession']) \
            -> FrozenSet[Flag]:
        """Get the full set of permanent and session flags for the message."""
        raise NotImplementedError


class LoadedMessage(Message):
    """A message with its contents loaded, such that it pulls the information
    from a message object necessary to gather `message attributes
    <https://tools.ietf.org/html/rfc3501#section-2.3>`_, as needed by the
    `FETCH responses <https://tools.ietf.org/html/rfc3501#section-7.4.2>`_.

    """

    @property
    def uid(self) -> int:
        """The message's unique identifier in the mailbox."""
        raise NotImplementedError

    @property
    def permanent_flags(self) -> Set[Flag]:
        """The message's set of permanent flags."""
        raise NotImplementedError

    @property
    def internal_date(self) -> Optional[datetime]:
        """The message's internal date."""
        raise NotImplementedError

    def get_flags(self, session: Optional['MailboxSession']) \
            -> FrozenSet[Flag]:
        """Get the full set of permanent and session flags for the message."""
        raise NotImplementedError

    def get_header(self, name: bytes) -> Sequence[Union[str, BaseHeader]]:
        """Get the values of a header from the message.

        Args:
            name: The name of the header.

        """
        raise NotImplementedError

    def get_headers(self, section: Iterable[int] = None,
                    subset: Iterable[bytes] = None,
                    inverse: bool = False) \
            -> Optional[bytes]:
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
        raise NotImplementedError

    def get_body(self, section: Iterable[int] = None) -> Optional[bytes]:
        """Get the full body of the message part, including headers.

        The ``section`` argument can index a nested sub-part of the message.
        For example, ``[2, 3]`` would get the 2nd sub-part of the message and
        then index it for its 3rd sub-part.

        Args:
            section: Optional nested list of sub-part indexes.

        """
        raise NotImplementedError

    def get_text(self, section: Iterable[int] = None) -> Optional[bytes]:
        """Get the text of the message part, not including headers.

        The ``section`` argument can index a nested sub-part of the message.
        For example, ``[2, 3]`` would get the 2nd sub-part of the message and
        then index it for its 3rd sub-part.

        Args:
            section: Optional nested list of sub-part indexes.

        """
        raise NotImplementedError

    def get_size(self) -> int:
        """Return the size of the message, in octets."""
        raise NotImplementedError

    def get_envelope_structure(self) -> EnvelopeStructure:
        """Build and return the envelope structure.

        See Also:
            `RFC 3501 2.3.5.
            <https://tools.ietf.org/html/rfc3501#section-2.3.5>`_

        """
        raise NotImplementedError

    def get_body_structure(self) -> BodyStructure:
        """Build and return the body structure.

        See Also:
            `RFC 3501 2.3.6
            <https://tools.ietf.org/html/rfc3501#section-2.3.6>`_

        """
        raise NotImplementedError
