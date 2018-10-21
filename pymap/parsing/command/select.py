import re
from typing import Tuple, Sequence, List, Iterable, cast, Optional

from . import CommandSelect, CommandNoArgs
from .. import NotParseable, Space, EndLine, Params
from ..primitives import Atom, ListP
from ..specials import AString, Mailbox, SequenceSet, Flag, FetchAttribute, \
    SearchKey, ExtensionOptions
from ..specials.flag import Recent
from ...flags import FlagOp

__all__ = ['CheckCommand', 'CloseCommand', 'ExpungeCommand', 'CopyCommand',
           'FetchCommand', 'StoreCommand', 'SearchCommand', 'UidCommand']


class CheckCommand(CommandNoArgs, CommandSelect):
    """The ``CHECK`` command initiates an implementation-specific backend
    synchronization for the selected mailbox.

    See Also:
       `RFC 3501 6.4.1. <https://tools.ietf.org/html/rfc3501#section-6.4.1>`_

    """

    command = b'CHECK'


class CloseCommand(CommandNoArgs, CommandSelect):
    """The ``CLOSE`` command closes a selected mailbox.

    See Also:
        `RFC 3501 6.4.2. <https://tools.ietf.org/html/rfc3501#section-6.4.2>`_

    """

    command = b'CLOSE'


class ExpungeCommand(CommandSelect):
    """The ``EXPUNGE`` command permanently erases all messages in the selected
    mailbox that contain the ``\\Deleted`` flag.

    See Also:
        `RFC 3501 6.4.3 <https://tools.ietf.org/html/rfc3501#section-6.4.3>`_
        `RFC 4315 2.1 <https://tools.ietf.org/html/rfc4315#section-2.1>`_

    Args:
        uid_set: Only the messages in the given UID set should be expunged.

    """

    command = b'EXPUNGE'

    def __init__(self, tag: bytes, uid_set: SequenceSet = None) -> None:
        super().__init__(tag)
        self.uid_set = uid_set

    @classmethod
    def parse(cls, buf: bytes, params: Params) \
            -> Tuple['ExpungeCommand', bytes]:
        uid_set: Optional[SequenceSet] = None
        if params.uid:
            _, buf = Space.parse(buf, params)
            uid_set, buf = SequenceSet.parse(buf, params)
        _, buf = EndLine.parse(buf, params)
        return cls(params.tag, uid_set), buf


class CopyCommand(CommandSelect):
    """The ``COPY`` command copies messages from the selected mailbox to the
    end of the destination mailbox.

    See Also:
        `RFC 3501 6.4.7. <https://tools.ietf.org/html/rfc3501#section-6.4.7>`_

    Args:
        tag: The command tag.
        seq_set: The sequence set of the messages to copy.
        mailbox: The destination mailbox.
        uid: True if the command should use message UIDs.

    """

    command = b'COPY'

    def __init__(self, tag: bytes, seq_set: SequenceSet,
                 mailbox: Mailbox, uid: bool) -> None:
        super().__init__(tag)
        self.sequence_set = seq_set
        self.mailbox_obj = mailbox
        self.uid = uid

    @property
    def mailbox(self) -> str:
        return str(self.mailbox_obj)

    @classmethod
    def parse(cls, buf: bytes, params: Params) -> Tuple['CopyCommand', bytes]:
        _, buf = Space.parse(buf, params)
        seq_set, buf = SequenceSet.parse(buf, params)
        _, buf = Space.parse(buf, params)
        mailbox, buf = Mailbox.parse(buf, params)
        _, buf = EndLine.parse(buf, params)
        return cls(params.tag, seq_set, mailbox, params.uid), buf


class FetchCommand(CommandSelect):
    """The ``FETCH`` command fetches message data from the selected mailbox.
    What data is fetched can be controlled in depth by a set of fetch
    attributes given in the command.

    See Also:
        `RFC 3501 6.4.5. <https://tools.ietf.org/html/rfc3501#section-6.4.5>`_

    Args:
        tag: The command tag.
        seq_set: The sequence set of the messages to fetch.
        attr_list: The message attributes to fetch.
        uid: True if the command should use message UIDs.

    """

    command = b'FETCH'

    def __init__(self, tag: bytes, seq_set: SequenceSet,
                 attr_list: Sequence[FetchAttribute], uid: bool,
                 options: ExtensionOptions) -> None:
        super().__init__(tag)
        self.sequence_set = seq_set
        self.no_expunge_response = not seq_set.uid
        self.attributes = attr_list
        self.uid = uid
        self.options = options

    @classmethod
    def _check_macros(cls, buf: bytes, params: Params):
        atom, after = Atom.parse(buf, params)
        macro = atom.value.upper()
        if macro == b'ALL':
            attrs = [FetchAttribute(b'FLAGS'),
                     FetchAttribute(b'INTERNALDATE'),
                     FetchAttribute(b'RFC822.SIZE'),
                     FetchAttribute(b'ENVELOPE')]
            return attrs, after
        elif macro == b'FULL':
            attrs = [FetchAttribute(b'FLAGS'),
                     FetchAttribute(b'INTERNALDATE'),
                     FetchAttribute(b'RFC822.SIZE'),
                     FetchAttribute(b'ENVELOPE'),
                     FetchAttribute(b'BODY')]
            return attrs, after
        elif macro == b'FAST':
            attrs = [FetchAttribute(b'FLAGS'),
                     FetchAttribute(b'INTERNALDATE'),
                     FetchAttribute(b'RFC822.SIZE')]
            return attrs, after
        raise NotParseable(buf)

    @classmethod
    def parse(cls, buf: bytes, params: Params) -> Tuple['FetchCommand', bytes]:
        _, buf = Space.parse(buf, params)
        seq_set, buf = SequenceSet.parse(buf, params)
        _, buf = Space.parse(buf, params)
        attr_list: List[FetchAttribute] = []
        try:
            attr_list, buf = cls._check_macros(buf, params)
        except NotParseable:
            pass
        try:
            attr, buf = FetchAttribute.parse(buf, params)
            attr_list = [attr]
        except NotParseable:
            pass
        if not attr_list:
            params_copy = params.copy(list_expected=[FetchAttribute])
            attr_list_p, buf = ListP.parse(buf, params_copy)
            attr_list = cast(List[FetchAttribute], attr_list_p.value)
        if params.uid:
            attr_list.append(FetchAttribute(b'UID'))
        options, buf = ExtensionOptions.parse(buf, params)
        _, buf = EndLine.parse(buf, params)
        return cls(params.tag, seq_set, attr_list, params.uid, options), buf


class StoreCommand(CommandSelect):
    """The ``STORE`` command updates the flags of a set of messages in the
    selected mailbox.

    See Also:
        `RFC 3501 6.4.6. <https://tools.ietf.org/html/rfc3501#section-6.4.6>`_

    Args:
        tag: The command tag.
        seq_set: The sequence set of the messages to fetch.
        flags: The flag set operand.
        mode: The type of update operation.
        uid: True if the command should use message UIDs.

    """

    command = b'STORE'

    _info_pattern = re.compile(br'^([+-]?)FLAGS(\.SILENT)?$', re.I)
    _modes = {b'': FlagOp.REPLACE, b'+': FlagOp.ADD, b'-': FlagOp.DELETE}

    def __init__(self, tag: bytes, seq_set: SequenceSet,
                 flags: Iterable[Flag], mode: FlagOp,
                 silent: bool, uid: bool,
                 options: ExtensionOptions) -> None:
        super().__init__(tag)
        self.sequence_set = seq_set
        self.flag_set = frozenset(flags) - {Recent}
        self.mode = mode
        self.silent = silent
        self.uid = uid
        self.options = options

    @classmethod
    def _parse_store_info(cls, buf: bytes, params: Params) \
            -> Tuple[FlagOp, bool, bytes]:
        info, after = Atom.parse(buf, params)
        match = cls._info_pattern.match(info.value)
        if not match:
            raise NotParseable(buf)
        mode = cls._modes[match.group(1)]
        silent = bool(match.group(2))
        return mode, silent, after

    @classmethod
    def _parse_flag_list(cls, buf: bytes, params: Params) \
            -> Tuple[Sequence[Flag], bytes]:
        flag_list: List[Flag] = []
        try:
            params_copy = params.copy(list_expected=[Flag])
            flag_list_p, buf = ListP.parse(buf, params_copy)
        except NotParseable:
            pass
        else:
            flag_list = cast(List[Flag], flag_list_p.value)
            return flag_list, buf
        while True:
            try:
                flag, buf = Flag.parse(buf, params)
                flag_list.append(flag)
                _, buf = Space.parse(buf, params)
            except NotParseable:
                return flag_list, buf

    @classmethod
    def parse(cls, buf: bytes, params: Params) -> Tuple['StoreCommand', bytes]:
        _, buf = Space.parse(buf, params)
        seq_set, buf = SequenceSet.parse(buf, params)
        options, buf = ExtensionOptions.parse(buf, params)
        _, buf = Space.parse(buf, params)
        mode, silent, buf = cls._parse_store_info(buf, params)
        _, buf = Space.parse(buf, params)
        flag_list, buf = cls._parse_flag_list(buf, params)
        _, buf = EndLine.parse(buf, params)
        return cls(params.tag, seq_set, flag_list, mode,
                   silent, params.uid, options), buf


class SearchCommand(CommandSelect):
    """The ``SEARCH`` command searches the messages in the selected mailbox
    based on a set of search criteria.

    See Also:
        `RFC 3501 6.4.4. <https://tools.ietf.org/html/rfc3501#section-6.4.4>`_

    Args:
        tag: The command tag.
        keys: The search keys.
        charset: The charset in use by the search keys.
        uid: True if the command should use message UIDs.

    """

    command = b'SEARCH'

    def __init__(self, tag: bytes, keys: Iterable[SearchKey],
                 charset: Optional[str], uid: bool,
                 options: ExtensionOptions) -> None:
        super().__init__(tag)
        self.keys = frozenset(keys)
        self.charset = charset
        self.uid = uid
        self.options = options

    @classmethod
    def _parse_charset(cls, buf: bytes, params: Params) \
            -> Tuple[Optional[str], bytes]:
        try:
            _, after = Space.parse(buf, params)
            atom, after = Atom.parse(after, params)
        except NotParseable:
            pass
        else:
            if atom.value.upper() == b'CHARSET':
                _, after = Space.parse(after, params)
                string, after = AString.parse(after, params)
                charset = str(string.value, 'ascii')
                try:
                    b' '.decode(charset)
                except LookupError:
                    raise NotParseable(buf, b'BADCHARSET')
                return charset, after
        return None, buf

    @classmethod
    def _parse_options(cls, buf: bytes, params: Params) \
            -> Tuple[ExtensionOptions, bytes]:
        start = cls._whitespace_length(buf)
        if buf[start:start + 6] == b'RETURN':
            return ExtensionOptions.parse(buf[start + 6:], params)
        else:
            options, _ = ExtensionOptions.parse(b'', params)
            return options, buf

    @classmethod
    def parse(cls, buf: bytes, params: Params) \
            -> Tuple['SearchCommand', bytes]:
        options, buf = cls._parse_options(buf, params)
        charset, buf = cls._parse_charset(buf, params)
        search_keys = []
        while True:
            try:
                _, buf = Space.parse(buf, params)
                key, buf = SearchKey.parse(buf, params.copy(charset=charset))
                search_keys.append(key)
            except NotParseable:
                if not search_keys:
                    raise
                break
        _, buf = EndLine.parse(buf, params)
        return cls(params.tag, search_keys, charset, params.uid, options), buf


class UidCommand(CommandSelect):
    """The ``UID`` command precedes one of the ``COPY``, ``EXPUNGE``,
    ``FETCH``, ``SEARCH``, or ``STORE`` commands and indicates that the
    command interacts with message UIDs instead of sequence numbers. Refer
    to the RFC section for a complete description.

    See Also:
        `RFC 3501 6.4.8 <https://tools.ietf.org/html/rfc3501#section-6.4.8>`_
        `RFC 4315 2.1 <https://tools.ietf.org/html/rfc4315#section-2.1>`_

    """

    command = b'UID'

    _allowed_subcommands = {b'COPY': CopyCommand,
                            b'EXPUNGE': ExpungeCommand,
                            b'FETCH': FetchCommand,
                            b'SEARCH': SearchCommand,
                            b'STORE': StoreCommand}

    @classmethod
    def _get_cmd(cls, name: bytes):
        return cls._allowed_subcommands.get(name.upper())

    @classmethod
    def parse(cls, buf: bytes, params: Params) -> Tuple[CommandSelect, bytes]:
        _, buf = Space.parse(buf, params)
        atom, after = Atom.parse(buf, params)
        cmd = cls._get_cmd(atom.value)
        if not cmd:
            raise NotParseable(buf)
        return cmd.parse(after, params.copy(uid=True))
