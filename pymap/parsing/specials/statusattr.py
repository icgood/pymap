
from __future__ import annotations

from .. import Params, Parseable, Space
from ..exceptions import NotParseable, InvalidContent
from ..primitives import Atom

__all__ = ['StatusAttribute']


class StatusAttribute(Parseable[bytes]):
    """Represents a status attribute from an IMAP stream.

    Args:
        status: The status attribute string.

    """

    #: The set of valid status attributes.
    valid_statuses = {b'MESSAGES', b'RECENT', b'UIDNEXT', b'UIDVALIDITY',
                      b'UNSEEN', b'MAILBOXID'}

    def __init__(self, status: bytes) -> None:
        super().__init__()
        status = status.upper()
        if status not in self.valid_statuses:
            raise ValueError(status)
        self.status = status

    @property
    def value(self) -> bytes:
        """The status attribute string."""
        return self.status

    @classmethod
    def parse(cls, buf: memoryview, params: Params) \
            -> tuple[StatusAttribute, memoryview]:
        try:
            _, buf = Space.parse(buf, params)
        except NotParseable:
            pass
        atom, after = Atom.parse(buf, params)
        try:
            return cls(atom.value), after
        except ValueError:
            raise InvalidContent(buf)

    def __hash__(self) -> int:
        return hash(self.value)

    def __eq__(self, other) -> bool:
        if isinstance(other, StatusAttribute):
            return self.value == other.value
        return super().__eq__(other)

    def __bytes__(self) -> bytes:
        return self.value
