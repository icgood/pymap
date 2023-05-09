
from __future__ import annotations

import os.path
from collections.abc import Iterable, Mapping
from typing import IO, Self

from pymap.parsing.specials.flag import Flag, Seen, Flagged, Deleted, Draft, \
    Answered

from .io import FileReadable

__all__ = ['MaildirFlags']


class MaildirFlags(FileReadable):
    """Maintains a set of IMAP keywords (non-standard flags) that are available
    for use on messages. This uses a custom file format to define keywords,
    which might look like this::

        0 $Junk
        1 $NonJunk

    The lower-case letter codes that correspond to each keyword start with
    ``'a'`` for 0, ``'b'`` for 1, etc. and up to 26 are supported.

    Args:
        keywords: The list of keywords available for use on messages.

    See Also:
        `IMAP Keywords
        <https://wiki.dovecot.org/MailboxFormat/Maildir#line-40>`_

    """

    _from_sys: Mapping[Flag, str] = {Seen: 'S',
                                     Flagged: 'F',
                                     Deleted: 'T',
                                     Draft: 'D',
                                     Answered: 'R'}

    _to_sys: Mapping[str, Flag] = {'S': Seen,
                                   'F': Flagged,
                                   'T': Deleted,
                                   'D': Draft,
                                   'R': Answered}

    def __init__(self, path: str) -> None:
        super().__init__(path)
        self._keywords: frozenset[Flag] = frozenset()
        self._to_kwd: Mapping[str, Flag] = {}
        self._from_kwd: Mapping[Flag, str] = {}

    @property
    def empty(self) -> bool:
        return not self._keywords

    @property
    def permanent_flags(self) -> frozenset[Flag]:
        """Return the set of all permanent flags, system and keyword."""
        return self.system_flags | self.keywords

    @property
    def system_flags(self) -> frozenset[Flag]:
        """Return the set of defined IMAP system flags."""
        return frozenset(self._from_sys.keys())

    @property
    def keywords(self) -> frozenset[Flag]:
        """Return the set of available IMAP keywords."""
        return self._keywords

    def to_maildir(self, flags: Iterable[bytes | Flag]) -> str:
        """Return the string of letter codes that are used to map to defined
        IMAP flags and keywords.

        Args:
            flags: The flags and keywords to map.

        """
        codes = []
        for flag in flags:
            if isinstance(flag, bytes):
                flag = Flag(flag)
            from_sys = self._from_sys.get(flag)
            if from_sys is not None:
                codes.append(from_sys)
            else:
                from_kwd = self._from_kwd.get(flag)
                if from_kwd is not None:
                    codes.append(from_kwd)
        return ''.join(codes)

    def from_maildir(self, codes: str) -> frozenset[Flag]:
        """Return the set of IMAP flags that correspond to the letter codes.

        Args:
            codes: The letter codes to map.

        """
        flags = set()
        for code in codes:
            if code == ',':
                break
            to_sys = self._to_sys.get(code)
            if to_sys is not None:
                flags.add(to_sys)
            else:
                to_kwd = self._to_kwd.get(code)
                if to_kwd is not None:
                    flags.add(to_kwd)
        return frozenset(flags)

    @classmethod
    def get_file(cls, path: str) -> str:
        return os.path.join(path, 'dovecot-keywords')

    @classmethod
    def get_default(cls, path: str) -> Self:
        return cls(path)

    @classmethod
    def open(cls, path: str, fp: IO[str]) -> Self:
        return cls(path)

    def read(self, fp: IO[str]) -> None:
        to_kwd = {}
        from_kwd = {}
        for line in fp:
            i, kwd = line.split()
            if kwd.startswith('\\'):
                raise ValueError(kwd)
            code = chr(ord('a') + int(i))
            flag = Flag(kwd)
            to_kwd[code] = flag
            from_kwd[flag] = code
        self._keywords = frozenset(from_kwd)
        self._to_kwd = to_kwd
        self._from_kwd = from_kwd
