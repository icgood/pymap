"""Defines convenience classes for working with IMAP flags.

See Also:
    `RFC 3501 2.3.2 <https://tools.ietf.org/html/rfc3501#section-2.3.2>`_

"""

import enum
from typing import Iterable, AbstractSet, FrozenSet, Dict

from .parsing.specials.flag import Flag, Recent, Wildcard

__all__ = ['FlagOp', 'PermanentFlags', 'SessionFlags']


class FlagOp(enum.Enum):
    """Types of operations when updating flags."""

    #: All existing flags should be replaced with the flag set.
    REPLACE = enum.auto()

    #: The flag set should be added to the existing set.
    ADD = enum.auto()

    #: The flag set should be removed from the existing set.
    DELETE = enum.auto()

    def apply(self, flag_set: AbstractSet[Flag], operand: Iterable[Flag]) \
            -> FrozenSet[Flag]:
        """Apply the flag operation on the two sets, returning the result.

        Args:
            flag_set: The flag set being operated on.
            operand: The flags to use as the operand.

        """
        operand_set = frozenset(operand)
        if self == FlagOp.ADD:
            return frozenset(flag_set | operand_set)
        elif self == FlagOp.DELETE:
            return frozenset(flag_set - operand_set)
        else:  # op == FlagOp.REPLACE
            return operand_set


class PermanentFlags:
    """Keeps track of the defined permanent flags on a mailbox. Because the
    permanent flags can include the special ``\\*`` wildcard flag, a simple
    set union operation is not enough to filter out unknown permanent flags.

    Args:
        defined: The defined session flags for the mailbox.

    """

    __slots__ = ['_defined']

    def __init__(self, defined: Iterable[Flag]) -> None:
        super().__init__()
        self._defined = frozenset(defined) - {Recent}

    @property
    def defined(self) -> FrozenSet[Flag]:
        """The defined permanent flags for the mailbox."""
        return self._defined

    def intersect(self, other: Iterable[Flag]) -> FrozenSet[Flag]:
        """Returns the subset of flags in ``other`` that are also in
        :attr:`.defined`. If the wildcard flag is defined, then all flags in
        ``other`` are returned.

        The ``&`` operator is an alias of this method, making these two
        calls equivalent::

            perm_flags.union(other_flags)
            perm_flags & other_flags

        Args:
            other: The operand flag set.

        """
        if Wildcard in self._defined:
            return frozenset(other)
        else:
            return self._defined & frozenset(other)

    def __and__(self, other: Iterable[Flag]) -> FrozenSet[Flag]:
        return self.intersect(other)


class SessionFlags:
    """Used to track session flags on a message. Session flags are only valid
    for the current IMAP client connection while it has the mailbox selected,
    they do not persist. The ``\\Recent`` flag is a special-case session flag.

    Args:
        defined: The defined session flags for the mailbox.

    """

    __slots__ = ['_defined', '_flags']

    def __init__(self, defined: Iterable[Flag]):
        super().__init__()
        self._defined = frozenset(defined) | {Recent}
        self._flags: Dict[int, FrozenSet[Flag]] = {}

    @property
    def defined(self) -> FrozenSet[Flag]:
        """The defined session flags for the mailbox."""
        return self._defined

    def intersect(self, other: Iterable[Flag]) -> FrozenSet[Flag]:
        """Returns the subset of flags in ``other`` that are also in
        :attr:`.defined`. If the wildcard flag is defined, then all flags in
        ``other`` are returned.

        The ``&`` operator is an alias of this method, making these two
        calls equivalent::

            session_flags.union(other_flags)
            session_flags & other_flags

        Args:
            other: The operand flag set.

        """
        if Wildcard in self._defined:
            return frozenset(other)
        else:
            return self._defined & frozenset(other)

    def __and__(self, other: Iterable[Flag]) -> FrozenSet[Flag]:
        return self.intersect(other)

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
        orig_set = self._flags.get(uid, frozenset())
        new_flags = op.apply(orig_set, self & flag_set)
        if Recent in orig_set:
            new_flags = new_flags | {Recent}
        else:
            new_flags = new_flags - {Recent}
        self._flags[uid] = new_flags
        return new_flags

    def add_recent(self, uid: int) -> FrozenSet[Flag]:
        """Adds the ``\\Recent`` flag to the flags for the session.

        Args:
            uid: The message UID value.

        """
        orig_set = self._flags.get(uid, frozenset())
        self._flags[uid] = new_flags = orig_set | {Recent}
        return new_flags

    @property
    def recent_uids(self) -> FrozenSet[int]:
        """The message UIDs with the ``\\Recent`` flag."""
        return frozenset(uid for uid, flags in self._flags.items()
                         if Recent in flags)
