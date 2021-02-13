
from __future__ import annotations

from datetime import datetime, tzinfo
from typing import Optional

from .. import Params, Parseable
from ..exceptions import InvalidContent
from ..primitives import QuotedString
from ...bytes import BytesFormat

__all__ = ['DateTime']


class DateTime(Parseable[datetime]):
    """Represents a date-time quoted string from an IMAP stream.

    Args:
        when: The date-time value.
        raw: The raw bytestring from IMAP parsing.

    """

    def __init__(self, when: datetime, raw: bytes = None) -> None:
        super().__init__()
        if when.tzinfo is None:
            when = when.replace(tzinfo=self.get_local_tzinfo())
        self.when = when
        self._raw = raw

    @property
    def value(self) -> datetime:
        """The date-time value."""
        return self.when

    @classmethod
    def get_local_tzinfo(cls) -> Optional[tzinfo]:
        """The system timezone, used when no timezone is specified."""
        return datetime.now().astimezone().tzinfo

    @classmethod
    def parse(cls, buf: memoryview, params: Params) \
            -> tuple[DateTime, memoryview]:
        string, after = QuotedString.parse(buf, params)
        try:
            when_str = str(string.value, 'ascii')
            when = datetime.strptime(when_str, '%d-%b-%Y %X %z')
        except (UnicodeDecodeError, ValueError):
            raise InvalidContent(buf)
        return cls(when, string.value), after

    def __bytes__(self) -> bytes:
        if self._raw is None:
            raw_str = self.value.strftime('%d-%b-%Y %X %z')
            self._raw = bytes(raw_str, 'ascii')
        return BytesFormat(b'"%b"') % (self._raw, )
