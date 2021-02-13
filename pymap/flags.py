"""Defines convenience classes for working with IMAP flags.

See Also:
    `RFC 3501 2.3.2 <https://tools.ietf.org/html/rfc3501#section-2.3.2>`_

"""

from __future__ import annotations

import enum
from collections.abc import Iterable, Mapping, Set

from .parsing.specials.flag import Flag, Recent, Wildcard

__all__ = ['FlagOp', 'PermanentFlags', 'SessionFlags']

_recent_set = frozenset({Recent})


class FlagOp(enum.Enum):
    """Types of operations when updating flags."""

    #: All existing flags should be replaced with the flag set.
    REPLACE = enum.auto()

    #: The flag set should be added to the existing set.
    ADD = enum.auto()

    #: The flag set should be removed from the existing set.
    DELETE = enum.auto()

    def __bytes__(self) -> bytes:
        return self.name.encode('ascii')

    def apply(self, flag_set: Set[Flag], operand: Set[Flag]) \
            -> frozenset[Flag]:
        """Apply the flag operation on the two sets, returning the result.

        Args:
            flag_set: The flag set being operated on.
            operand: The flags to use as the operand.

        """
        if self == FlagOp.ADD:
            return frozenset(flag_set | operand)
        elif self == FlagOp.DELETE:
            return frozenset(flag_set - operand)
        else:  # op == FlagOp.REPLACE
            return frozenset(operand)


class PermanentFlags:
    """Keeps track of the defined permanent flags on a mailbox. Because the
    permanent flags can include the special ``\\*`` wildcard flag, a simple
    set intersect operation is not enough to filter out unknown permanent
    flags.

    Args:
        defined: The defined session flags for the mailbox.

    """

    __slots__ = ['_defined']

    def __init__(self, defined: Iterable[Flag]) -> None:
        super().__init__()
        self._defined = frozenset(defined) - _recent_set

    @property
    def defined(self) -> frozenset[Flag]:
        """The defined permanent flags for the mailbox."""
        return self._defined

    def intersect(self, other: Iterable[Flag]) -> frozenset[Flag]:
        """Returns the subset of flags in ``other`` that are also in
        :attr:`.defined`. If the wildcard flag is defined, then all flags in
        ``other`` are returned.

        The ``&`` operator is an alias of this method, making these two
        calls equivalent::

            perm_flags.intersect(other_flags)
            perm_flags & other_flags

        Args:
            other: The operand flag set.

        """
        if Wildcard in self._defined:
            return frozenset(other)
        else:
            return self._defined & frozenset(other)

    def __and__(self, other: Iterable[Flag]) -> frozenset[Flag]:
        return self.intersect(other)


class SessionFlags:
    """Used to track session flags on a message. Session flags are only valid
    for the current IMAP client connection while it has the mailbox selected,
    they do not persist. The ``\\Recent`` flag is a special-case session flag.

    Args:
        defined: The defined session flags for the mailbox.

    """

    __slots__ = ['_defined', '_flags', '_recent']

    def __init__(self, defined: Iterable[Flag]):
        super().__init__()
        self._defined = frozenset(defined) - _recent_set
        self._flags: dict[int, frozenset[Flag]] = {}
        self._recent: set[int] = set()

    @property
    def defined(self) -> frozenset[Flag]:
        """The defined session flags for the mailbox."""
        return self._defined

    def intersect(self, other: Iterable[Flag]) -> frozenset[Flag]:
        """Returns the subset of flags in ``other`` that are also in
        :attr:`.defined`. If the wildcard flag is defined, then all flags in
        ``other`` are returned.

        The ``&`` operator is an alias of this method, making these two
        calls equivalent::

            session_flags.intersect(other_flags)
            session_flags & other_flags

        Args:
            other: The operand flag set.

        """
        if Wildcard in self._defined:
            return frozenset(other)
        else:
            return self._defined & frozenset(other)

    def __and__(self, other: Iterable[Flag]) -> frozenset[Flag]:
        return self.intersect(other)

    def get(self, uid: int) -> frozenset[Flag]:
        """Return the session flags for the mailbox session.

        Args:
            uid: The message UID value.

        """
        recent = _recent_set if uid in self._recent else frozenset()
        flags = self._flags.get(uid)
        return recent if flags is None else (flags | recent)

    def remove(self, uids: Iterable[int]) -> None:
        """Remove any session flags for the given message.

        Args:
            uids: The message UID values.

        """
        for uid in uids:
            self._recent.discard(uid)
            self._flags.pop(uid, None)

    def update(self, uid: int, flag_set: Iterable[Flag],
               op: FlagOp = FlagOp.REPLACE) -> frozenset[Flag]:
        """Update the flags for the session, returning the resulting flags.

        Args:
            uid: The message UID value.
            flag_set: The set of flags for the update operation.
            op: The type of update.

        """
        orig_set = self._flags.get(uid, frozenset())
        new_flags = op.apply(orig_set, self & flag_set)
        if new_flags:
            self._flags[uid] = new_flags
        else:
            self._flags.pop(uid, None)
        return new_flags

    def add_recent(self, uid: int) -> None:
        """Adds the ``\\Recent`` flag to the flags for the session.

        Args:
            uid: The message UID value.

        """
        self._recent.add(uid)

    @property
    def recent(self) -> int:
        """The number of messages with the ``\\Recent`` flag."""
        return len(self._recent)

    @property
    def recent_uids(self) -> Set[int]:
        """The message UIDs with the ``\\Recent`` flag."""
        return self._recent

    @property
    def flags(self) -> Mapping[int, frozenset[Flag]]:
        """The mapping of UID to its associated session flags, not including
        ``\\Recent``.

        """
        return self._flags
