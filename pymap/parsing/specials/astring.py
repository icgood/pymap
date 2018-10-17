import re
from typing import Tuple

from .. import Params, Special
from ..primitives import String, QuotedString

__all__ = ['AString']


class AString(Special[bytes]):
    """Represents a string that may have quotes (like a quoted-string) or may
    not (like an atom).  Additionally allows the closing square bracket (``]``)
    character in the unquoted form.

    Args:
        string: The string value.
        raw: The raw bytestring from IMAP parsing.

    Attributes:
        string: The string value.

    """

    _pattern = re.compile(br'[\x21\x23\x24\x26\x27\x2B-\x5B'
                          br'\x5D\x5E-\x7A\x7C\x7E]+')

    def __init__(self, string: bytes, raw: bytes = None) -> None:
        super().__init__()
        self.string = string
        self._raw = raw

    @property
    def value(self) -> bytes:
        """The string value."""
        return self.string

    @classmethod
    def parse(cls, buf: bytes, params: Params) -> Tuple['AString', bytes]:
        start = cls._whitespace_length(buf)
        match = cls._pattern.match(buf, start)
        if match:
            buf = buf[match.end(0):]
            return cls(match.group(0), match.group(0)), buf
        string, buf = String.parse(buf, params)
        return cls(string.value, bytes(string)), buf

    def __bytes__(self):
        if self._raw is not None:
            return self._raw
        match = self._pattern.fullmatch(self.value)
        if match:
            return self.value
        else:
            return bytes(QuotedString(self.value))
