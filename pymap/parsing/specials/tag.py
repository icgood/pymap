import re
from typing import Tuple

from .. import NotParseable, Params, Special

__all__ = ['Tag']


class Tag(Special[bytes]):
    """Represents the tag prefixed to every client command in an IMAP stream.

    Args:
        tag: The tag value.

    """

    _pattern = re.compile(br'[\x21\x23\x24\x26\x27\x2C-\x5B'
                          br'\x5D\x5E-\x7A\x7C\x7E]+')

    def __init__(self, tag: bytes) -> None:
        super().__init__()
        self.tag = tag

    @property
    def value(self) -> bytes:
        """The tag value."""
        return self.tag

    @classmethod
    def parse(cls, buf: bytes, params: Params) -> Tuple['Tag', bytes]:
        start = cls._whitespace_length(buf)
        match = cls._pattern.match(buf, start)
        if not match:
            raise NotParseable(buf)
        return cls(match.group(0)), buf[match.end(0):]

    def __bytes__(self) -> bytes:
        return self.value
