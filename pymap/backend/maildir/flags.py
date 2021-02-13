
from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import IO, TypeVar, Union

from pymap.parsing.specials.flag import Flag, Seen, Flagged, Deleted, Draft, \
    Answered

from .io import FileReadable

__all__ = ['MaildirFlags']

_MFT = TypeVar('_MFT', bound='MaildirFlags')


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

    def __init__(self, keywords: Sequence[Flag]) -> None:
        super().__init__()
        if len(keywords) > 26:
            raise ValueError(keywords)
        self._keywords = frozenset(keywords)
        self._to_kwd = {chr(ord('a') + i): kwd
                        for i, kwd in enumerate(keywords)}
        self._from_kwd = {kwd: chr(ord('a') + i)
                          for i, kwd in enumerate(keywords)}

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

    def to_maildir(self, flags: Iterable[Union[bytes, Flag]]) -> str:
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
    def get_file(cls) -> str:
        return 'dovecot-keywords'

    @classmethod
    def get_default(cls: type[_MFT], base_dir: str) -> _MFT:
        return cls([])

    @classmethod
    def open(cls: type[_MFT], base_dir: str, fp: IO[str]) -> _MFT:
        ret = []
        for line in fp:
            i, kwd = line.split()
            if kwd.startswith('\\'):
                raise ValueError(kwd)
            ret.append((i, kwd))
        return cls([Flag(kwd) for _, kwd in sorted(ret)])
