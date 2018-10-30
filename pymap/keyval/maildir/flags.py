from typing import Iterable, Union, List, FrozenSet

from pymap.parsing.specials import Flag

__all__ = ['get_permanent_flags', 'flags_from_imap', 'flags_from_maildir']


_from_imap_table = {br'\Seen': 'S',
                    br'\Flagged': 'F',
                    br'\Deleted': 'T',
                    br'\Draft': 'D',
                    br'\Answered': 'R'}


_from_maildir_table = {'S': Flag(br'\Seen'),
                       'F': Flag(br'\Flagged'),
                       'T': Flag(br'\Deleted'),
                       'D': Flag(br'\Draft'),
                       'R': Flag(br'\Answered')}


def get_permanent_flags() -> FrozenSet[Flag]:
    """Set of all supported permanent flags."""
    return frozenset({Flag(flag) for flag in _from_imap_table.keys()})


def flags_from_imap(flags: Iterable[Union[bytes, Flag]]) -> str:
    """Given a list of IMAP-style flags, e.g. ``\\Seen``, return a correlating
    list of :py:class:`~mailbox.MaildirMessage` flags, in the form of a string.
    Unrecognized flags are ignored.

    Args:
        flags: List of flags, each can either be bytestring or a
            :class:`~pymap.parsing.specials.Flag`.

    """
    ret: List[str] = []
    for flag in flags:
        if isinstance(flag, Flag):
            flag = flag.value
        maildir_flag = _from_imap_table.get(flag)
        if maildir_flag:
            ret.append(maildir_flag)
    return ''.join(ret)


def flags_from_maildir(flags: str) -> FrozenSet[Flag]:
    """Given a string of :py:class:`~mailbox.MaildirMessage` flags, return a
    correlating set of :class:`~pymap.parsing.specials.Flag` objects.
    Unrecognized flags are ignored.

    Args:
        flags: String of flags, as would be returned by
            :py:class:`~mailbox.MaildirMessage.get_flags`.

    """
    ret: List[Flag] = []
    for flag in flags:
        imap_flag = _from_maildir_table.get(flag)
        if imap_flag:
            ret.append(imap_flag)
    return frozenset(ret)
