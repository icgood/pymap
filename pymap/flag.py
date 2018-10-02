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

"""Defines convenience classes for working with IMAP flags.

.. seealso::

   `RFC 3501 2.3.2 <https://tools.ietf.org/html/rfc3501#section-2.3.2>`_

"""

import enum
from typing import AbstractSet, FrozenSet, Dict

from .parsing.specials.flag import Flag

__all__ = ['FlagOp', 'Flag', 'CustomFlag', 'SessionFlags', 'Seen', 'Recent',
           'Deleted', 'Flagged', 'Answered', 'Draft']


class FlagOp(enum.Enum):
    """Types of operations when updating flags."""

    #: All existing flags should be replaced with the flag set.
    REPLACE = enum.auto()

    #: The flag set should be added to the existing set.
    ADD = enum.auto()

    #: The flag set should be removed from the existing set.
    DELETE = enum.auto()


class CustomFlag(Flag):
    """Base class for defining custom flag objects. All custom flags, whether
    they are instances or sub-classes, should use this class.

    :param value: The bytes of the flag's value.

    """

    def __init__(self, value: bytes) -> None:
        super().__init__(value)


class SessionFlags:
    """Used to track session flags on a message. Stored as a weak-key
    dictionary. The key can be any value, but it is typically a
    :class:`~pymap.interfaces.message.Message`.

    """

    def __init__(self):
        self._flags: Dict[int, FrozenSet[Flag]] = {}

    def get(self, uid: int) -> FrozenSet[Flag]:
        """Return the session flags for the mailbox session.

        :param uid: The message UID value.

        """
        return self._flags.get(uid, frozenset())

    def remove(self, uid: int) -> None:
        """Remove any session flags for the given message.

        :param uid: The message UID value.

        """
        self._flags.pop(uid, None)

    def update(self, uid: int, flag_set: AbstractSet[Flag],
               op: FlagOp = FlagOp.REPLACE) -> FrozenSet[Flag]:
        """Update the flags for the session.

        :param uid: The message UID value.
        :param flag_set: The set of flags for the update operation.
        :param op: The type of update.

        """
        session_flags = self._flags.get(uid, frozenset())
        if op == FlagOp.ADD:
            session_flags = session_flags | flag_set
        elif op == FlagOp.DELETE:
            session_flags = session_flags - flag_set
        else:  # op == FlagOp.REPLACE
            session_flags = frozenset(flag_set)
        self._flags[uid] = session_flags
        return session_flags

    def add_recent(self, uid: int) -> FrozenSet[Flag]:
        """Adds the ``\\Recent`` flag to the flags for the session.

        :param uid: The message UID value.

        """
        return self.update(uid, {Recent}, FlagOp.ADD)

    def count_recent(self) -> int:
        """Count the number of messages with the ``\\Recent`` flag."""
        count = 0
        for flags in self._flags.values():
            if Recent in flags:
                count += 1
        return count


Seen = Flag(br'\Seen')
Recent = Flag(br'\Recent')
Deleted = Flag(br'\Deleted')
Flagged = Flag(br'\Flagged')
Answered = Flag(br'\Answered')
Draft = Flag(br'\Draft')
