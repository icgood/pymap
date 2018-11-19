
import re
from typing import Tuple, Sequence, List, Iterable, Optional, ClassVar

from . import CommandSelect, CommandNoArgs
from .. import Params, Space, EndLine
from ..exceptions import NotParseable, CommandInvalid
from ..primitives import Atom, ListP
from ..specials import AString, Mailbox, SequenceSet, Flag, FetchAttribute, \
    SearchKey, ExtensionOptions
from ...flags import FlagOp

__all__ = ['CheckCommand', 'CloseCommand', 'ExpungeCommand', 'CopyCommand',
           'FetchCommand', 'StoreCommand', 'SearchCommand', 'UidCommand',
           'UidCopyCommand', 'UidExpungeCommand', 'UidFetchCommand',
           'UidSearchCommand', 'UidStoreCommand', 'IdleCommand']


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
        tag: The command tag.
        uid_set: Only the messages in the given UID set should be expunged.

    """

    command = b'EXPUNGE'
    uid: ClassVar[bool] = False

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

    """

    command = b'COPY'
    uid: ClassVar[bool] = False

    def __init__(self, tag: bytes, seq_set: SequenceSet,
                 mailbox: Mailbox) -> None:
        super().__init__(tag)
        self.sequence_set = seq_set
        self.mailbox_obj = mailbox

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
        return cls(params.tag, seq_set, mailbox), buf


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

    """

    command = b'FETCH'
    uid: ClassVar[bool] = False

    def __init__(self, tag: bytes, seq_set: SequenceSet,
                 attr_list: Sequence[FetchAttribute],
                 options: ExtensionOptions = None) -> None:
        super().__init__(tag)
        self.sequence_set = seq_set
        self.no_expunge_response = not seq_set.uid
        self.attributes = attr_list
        self.options = options or ExtensionOptions.empty()

    @classmethod
    def _check_macros(cls, buf: bytes, params: Params) \
            -> Tuple[Sequence[FetchAttribute], bytes]:
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
        attr_list: Sequence[FetchAttribute] = []
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
            attr_list = attr_list_p.get_as(FetchAttribute)
        if params.uid:
            attr_list = list(attr_list) + [FetchAttribute(b'UID')]
        options, buf = ExtensionOptions.parse(buf, params)
        _, buf = EndLine.parse(buf, params)
        return cls(params.tag, seq_set, attr_list, options), buf


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

    """

    command = b'STORE'
    uid: ClassVar[bool] = False

    _info_pattern = re.compile(br'^([+-]?)FLAGS(\.SILENT)?$', re.I)
    _modes = {b'': FlagOp.REPLACE, b'+': FlagOp.ADD, b'-': FlagOp.DELETE}

    def __init__(self, tag: bytes, seq_set: SequenceSet,
                 flags: Iterable[Flag], mode: FlagOp,
                 silent: bool, options: ExtensionOptions = None) -> None:
        super().__init__(tag)
        self.sequence_set = seq_set
        self.flag_set = frozenset(flags)
        self.mode = mode
        self.silent = silent
        self.options = options or ExtensionOptions.empty()

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
        try:
            params_copy = params.copy(list_expected=[Flag])
            flag_list_p, buf = ListP.parse(buf, params_copy)
        except NotParseable:
            pass
        else:
            return flag_list_p.get_as(Flag), buf
        flag_list: List[Flag] = []
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
        return cls(params.tag, seq_set, flag_list, mode, silent, options), buf


class SearchCommand(CommandSelect):
    """The ``SEARCH`` command searches the messages in the selected mailbox
    based on a set of search criteria.

    See Also:
        `RFC 3501 6.4.4. <https://tools.ietf.org/html/rfc3501#section-6.4.4>`_

    Args:
        tag: The command tag.
        keys: The search keys.
        charset: The charset in use by the search keys.

    """

    command = b'SEARCH'
    uid: ClassVar[bool] = False

    def __init__(self, tag: bytes, keys: Iterable[SearchKey],
                 charset: Optional[str],
                 options: ExtensionOptions = None) -> None:
        super().__init__(tag)
        self.keys = frozenset(keys)
        self.charset = charset
        self.options = options or ExtensionOptions.empty()

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
        return cls(params.tag, search_keys, charset, options), buf


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
    compound = True

    @classmethod
    def parse(cls, buf: bytes, params: Params) -> Tuple['UidCommand', bytes]:
        raise NotImplementedError


class UidCopyCommand(CopyCommand):
    """The ``UID COPY`` variant of the ``COPY`` command, which uses message
    UIDs instead of sequence numbers.

    """

    command = b'UID COPY'
    delegate = CopyCommand
    uid = True

    @classmethod
    def parse(cls, buf: bytes, params: Params) \
            -> Tuple['UidCopyCommand', bytes]:
        ret, buf = super().parse(buf, params.copy(uid=True))
        if not isinstance(ret, UidCopyCommand):
            raise TypeError(ret)
        return ret, buf


class UidExpungeCommand(ExpungeCommand):
    """The ``UID EXPUNGE`` variant of the ``EXPUNGE`` command, which uses
    message UIDs instead of sequence numbers.

    """

    command = b'UID EXPUNGE'
    delegate = ExpungeCommand
    uid = True

    @classmethod
    def parse(cls, buf: bytes, params: Params) \
            -> Tuple['UidExpungeCommand', bytes]:
        ret, buf = super().parse(buf, params.copy(uid=True))
        if not isinstance(ret, UidExpungeCommand):
            raise TypeError(ret)
        return ret, buf


class UidFetchCommand(FetchCommand):
    """The ``UID FETCH`` variant of the ``FETCH`` command, which uses message
    UIDs instead of sequence numbers.

    """

    command = b'UID FETCH'
    delegate = FetchCommand
    uid = True

    @classmethod
    def parse(cls, buf: bytes, params: Params) \
            -> Tuple['UidFetchCommand', bytes]:
        ret, buf = super().parse(buf, params.copy(uid=True))
        if not isinstance(ret, UidFetchCommand):
            raise TypeError(ret)
        return ret, buf


class UidSearchCommand(SearchCommand):
    """The ``UID SEARCH`` variant of the ``SEARCH`` command, which uses message
    UIDs instead of sequence numbers.

    """

    command = b'UID SEARCH'
    delegate = SearchCommand
    uid = True

    @classmethod
    def parse(cls, buf: bytes, params: Params) \
            -> Tuple['UidSearchCommand', bytes]:
        ret, buf = super().parse(buf, params.copy(uid=True))
        if not isinstance(ret, UidSearchCommand):
            raise TypeError(ret)
        return ret, buf


class UidStoreCommand(StoreCommand):
    """The ``UID STORE`` variant of the ``STORE`` command, which uses message
    UIDs instead of sequence numbers.

    """

    command = b'UID STORE'
    delegate = StoreCommand
    uid = True

    @classmethod
    def parse(cls, buf: bytes, params: Params) \
            -> Tuple['UidStoreCommand', bytes]:
        ret, buf = super().parse(buf, params.copy(uid=True))
        if not isinstance(ret, UidStoreCommand):
            raise TypeError(ret)
        return ret, buf


class IdleCommand(CommandSelect):
    """The ``IDLE`` command waits for the continuation string ``DONE`` from the
    client. During this wait, the server may be sending untagged responses
    indicating concurrent updates to the mailbox.

    Parsing this command is a special case. The continuation string ``DONE`` is
    actually parsed by the :meth:`.parse_done` method. The :meth:`.parse`
    only parses the ``IDLE <CRLF>`` portion, and does not raise a
    :exc:`~pymap.exceptions.RequiresContinuation` exception.

    See Also:
        `RFC 2177 <https://tools.ietf.org/html/rfc2177>`_

    """

    command = b'IDLE'

    #: The string used to end the command.
    continuation = b'DONE'

    @classmethod
    def parse(cls, buf: bytes, params: Params) -> Tuple['IdleCommand', bytes]:
        _, buf = EndLine.parse(buf, params)
        return cls(params.tag), buf

    def parse_done(self, buf: bytes, params: Params) -> bytes:
        try:
            cont_len = len(self.continuation)
            if buf[0:cont_len].upper() != self.continuation:
                raise NotParseable(buf)
            _, buf = EndLine.parse(buf[cont_len:], params)
            return buf
        except NotParseable as exc:
            raise CommandInvalid(params.tag, self.command) from exc
