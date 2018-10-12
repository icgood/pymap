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

        :param name: The name of the header.

        """
        raise NotImplementedError

    def get_headers(self, section: Optional[Iterable[int]] = None,
                    subset: Iterable[bytes] = None,
                    inverse: bool = False) \
            -> Optional[bytes]:
        """Get the headers from the message.

        The ``section`` argument can index a nested sub-part of the message.
        For example, ``[2, 3]`` would get the 2nd sub-part of the message and
        then index it for its 3rd sub-part.

        :param section: Optional nested list of sub-part indexes.
        :param subset: Subset of headers to get.
        :param inverse: If ``subset`` is given, this flag will invert it
                             so that the headers *not* in ``subset`` are
                             returned.

        """
        raise NotImplementedError

    def get_body(self, section: Optional[Iterable[int]] = None) \
            -> Optional[bytes]:
        """Get the full body of the message part, including headers.

        The ``section`` argument can index a nested sub-part of the message.
        For example, ``[2, 3]`` would get the 2nd sub-part of the message and
        then index it for its 3rd sub-part.

        :param section: Optional nested list of sub-part indexes.

        """
        raise NotImplementedError

    def get_text(self, section: Optional[Iterable[int]] = None) \
            -> Optional[bytes]:
        """Get the text of the message part, not including headers.

        The ``section`` argument can index a nested sub-part of the message.
        For example, ``[2, 3]`` would get the 2nd sub-part of the message and
        then index it for its 3rd sub-part.

        :param section: Optional nested list of sub-part indexes.

        """
        raise NotImplementedError

    def get_size(self) -> int:
        """Return the size of the message, in octets."""
        raise NotImplementedError

    def get_envelope_structure(self) -> EnvelopeStructure:
        """Build and return the envelope structure.

        .. seealso::

           `RFC 3501 2.3.5
           <https://tools.ietf.org/html/rfc3501#section-2.3.5>`_

        """
        raise NotImplementedError

    def get_body_structure(self) -> BodyStructure:
        """Build and return the body structure.

        .. seealso::

           `RFC 3501 2.3.6
           <https://tools.ietf.org/html/rfc3501#section-2.3.6>`_

        """
        raise NotImplementedError
