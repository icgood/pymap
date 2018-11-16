"""Defines convenience classes for working with IMAP flags.

See Also:
    `RFC 3501 2.3.2 <https://tools.ietf.org/html/rfc3501#section-2.3.2>`_

"""

import enum
from typing import Iterable, FrozenSet, Dict

from .parsing.specials.flag import Flag, Recent

__all__ = ['FlagOp', 'SessionFlags']


class FlagOp(enum.Enum):
    """Types of operations when updating flags."""

    #: All existing flags should be replaced with the flag set.
    REPLACE = enum.auto()

    #: The flag set should be added to the existing set.
    ADD = enum.auto()

    #: The flag set should be removed from the existing set.
    DELETE = enum.auto()


class SessionFlags:
    """Used to track session flags on a message. Stored as a weak-key
    dictionary. The key can be any value, but it is typically a
    :class:`~pymap.interfaces.message.Message`.

    """

    def __init__(self):
        self._flags: Dict[int, FrozenSet[Flag]] = {}

    def __getitem__(self, uid: int) -> FrozenSet[Flag]:
        return self.get(uid)

    def __delitem__(self, uid: int) -> None:
        self.remove(uid)

    def __setitem__(self, uid: int, flag_set: Iterable[Flag]) -> None:
        self.update(uid, flag_set)

    def get(self, uid: int) -> FrozenSet[Flag]:
        """Return the session flags for the mailbox session.

        Args:
            uid: The message UID value.

        """
        return self._flags.get(uid, frozenset())

    def remove(self, uid: int) -> None:
        """Remove any session flags for the given message.

        Args:
            uid: The message UID value.

        """
        self._flags.pop(uid, None)

    def update(self, uid: int, flag_set: Iterable[Flag],
               op: FlagOp = FlagOp.REPLACE) -> FrozenSet[Flag]:
        """Update the flags for the session, returning the resulting flags.

        Args:
            uid: The message UID value.
            flag_set: The set of flags for the update operation.
            op: The type of update.

        """
        session_flags = self._flags.get(uid, frozenset())
        if op == FlagOp.ADD:
            session_flags = session_flags | frozenset(flag_set)
        elif op == FlagOp.DELETE:
            session_flags = session_flags - frozenset(flag_set)
        else:  # op == FlagOp.REPLACE
            session_flags = frozenset(flag_set)
        self._flags[uid] = session_flags
        return session_flags

    def add_recent(self, uid: int) -> FrozenSet[Flag]:
        """Adds the ``\\Recent`` flag to the flags for the session.

        Args:
            uid: The message UID value.

        """
        return self.update(uid, {Recent}, FlagOp.ADD)

    def count_recent(self) -> int:
        """Count the number of messages with the ``\\Recent`` flag."""
        count = 0
        for flags in self._flags.values():
            if Recent in flags:
                count += 1
        return count
