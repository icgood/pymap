
from __future__ import annotations

from typing import Optional

from . import AString
from .. import Params, Parseable
from ..modutf7 import modutf7_encode, modutf7_decode

__all__ = ['Mailbox']


class Mailbox(Parseable[str]):
    """Represents a mailbox data object from an IMAP stream.

    Args:
        mailbox: The mailbox name.

    """

    def __init__(self, mailbox: str) -> None:
        super().__init__()
        if mailbox.upper() == 'INBOX':
            self.mailbox = 'INBOX'
            self._raw: Optional[bytes] = b'INBOX'
        else:
            self.mailbox = mailbox
            self._raw = None

    @property
    def value(self) -> str:
        """The mailbox name."""
        return self.mailbox

    @classmethod
    def parse(cls, buf: memoryview, params: Params) \
            -> tuple[Mailbox, memoryview]:
        atom, buf = AString.parse(buf, params)
        mailbox = atom.value
        if mailbox.upper() == b'INBOX':
            return cls('INBOX'), buf
        return cls(modutf7_decode(mailbox)), buf

    def __bytes__(self) -> bytes:
        if self._raw is not None:
            return self._raw
        self._raw = raw = bytes(AString(modutf7_encode(self.value)))
        return raw

    def __str__(self) -> str:
        return self.value
