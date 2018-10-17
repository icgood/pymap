from datetime import datetime
from typing import Tuple

from .. import Params, Special, InvalidContent
from ..primitives import QuotedString

__all__ = ['DateTime']


class DateTime(Special[datetime]):
    """Represents a date-time quoted string from an IMAP stream.

    Args:
        when: The date-time value.
        raw: The raw bytestring from IMAP parsing.

    """

    def __init__(self, when: datetime, raw: bytes = None) -> None:
        super().__init__()
        self.when = when
        self._raw = raw

    @property
    def value(self) -> datetime:
        """The date-time value."""
        return self.when

    @classmethod
    def parse(cls, buf: bytes, params: Params) -> Tuple['DateTime', bytes]:
        string, after = QuotedString.parse(buf, params)
        try:
            when_str = str(string.value, 'ascii')
            when = datetime.strptime(when_str, '%d-%b-%Y %X %z')
        except (UnicodeDecodeError, ValueError):
            raise InvalidContent(buf)
        return cls(when, string.value), after

    def __bytes__(self) -> bytes:
        if self._raw is None:
            if self.value.tzinfo is None:
                raw_str = self.value.strftime('%d-%b-%Y %X')
            else:
                raw_str = self.value.strftime('%d-%b-%Y %X %z')
            self._raw = bytes(raw_str, 'ascii')
        return b'"%b"' % self._raw
