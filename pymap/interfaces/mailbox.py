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

from typing import TYPE_CHECKING, Optional, AbstractSet, FrozenSet

from .message import Message
from ..flag import FlagOp
from ..parsing.specials import Flag

__all__ = ['MailboxInterface']

if TYPE_CHECKING:
    from ..mailbox import MailboxSession


class MailboxInterface:
    """Corresponds to a mailbox state on an IMAP session, since the last
    update from the backend.

    """

    def update_flags(self, session: 'MailboxSession', message: Message,
                     flag_set: AbstractSet[Flag],
                     flag_op: FlagOp = FlagOp.REPLACE) \
            -> FrozenSet[Flag]:
        """Update the flags on a message in the mailbox. After this call,
        the ``message.permanent_flags`` set should be persisted by the
        backend.

        :param session: The mailbox session.
        :param message: The message to set flags on.
        :param flag_set: The set of flags for the update operation.
        :param flag_op: The mode to change the flags.

        """
        raise NotImplementedError

    @property
    def name(self) -> str:
        """The name of the mailbox."""
        raise NotImplementedError

    @property
    def readonly(self) -> bool:
        """Whether the mailbox is read-only or read-write."""
        raise NotImplementedError

    @property
    def permanent_flags(self) -> FrozenSet[Flag]:
        """The permanent flags allowed in the mailbox."""
        raise NotImplementedError

    @property
    def session_flags(self) -> FrozenSet[Flag]:
        """The session flags allowed in the mailbox."""
        raise NotImplementedError

    @property
    def flags(self) -> FrozenSet[Flag]:
        """Set of all permanent and session flags available on the mailbox."""
        raise NotImplementedError

    @property
    def exists(self) -> int:
        """Number of total messages in the mailbox."""
        raise NotImplementedError

    @property
    def recent(self) -> int:
        """Number of recent messages in the mailbox."""
        raise NotImplementedError

    @property
    def unseen(self) -> int:
        """Number of unseen messages in the mailbox."""
        raise NotImplementedError

    @property
    def first_unseen(self) -> Optional[int]:
        """The sequence number of the first unseen message."""
        raise NotImplementedError

    @property
    def next_uid(self) -> int:
        """The predicted next message UID."""
        raise NotImplementedError

    @property
    def uid_validity(self) -> int:
        """The mailbox UID validity value."""
        raise NotImplementedError
