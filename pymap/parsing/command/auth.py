import re
from datetime import datetime
from typing import Tuple, Sequence, Iterable, Optional, List

from . import CommandAuth
from .. import NotParseable, UnexpectedType, Space, EndLine, Params
from ..exceptions import InvalidContent
from ..primitives import ListP, String, LiteralString
from ..specials import Mailbox, DateTime, Flag, StatusAttribute, \
    ExtensionOption, ExtensionOptions
from ...message import AppendMessage

__all__ = ['AppendCommand', 'CreateCommand', 'DeleteCommand', 'ExamineCommand',
           'ListCommand', 'LSubCommand', 'RenameCommand', 'SelectCommand',
           'StatusCommand', 'SubscribeCommand', 'UnsubscribeCommand']

_AppendMsgArg = Tuple[bytes, Iterable[Flag], Optional[datetime],
                      ExtensionOptions]


class CommandMailboxArg(CommandAuth):

    def __init__(self, tag: bytes, mailbox: Mailbox) -> None:
        super().__init__(tag)
        self.mailbox_obj = mailbox

    @property
    def mailbox(self) -> str:
        return str(self.mailbox_obj)

    @classmethod
    def parse(cls, buf: bytes, params: Params) \
            -> Tuple['CommandMailboxArg', bytes]:
        _, buf = Space.parse(buf, params)
        mailbox, buf = Mailbox.parse(buf, params)
        _, buf = EndLine.parse(buf, params)
        return cls(params.tag, mailbox), buf


class AppendCommand(CommandAuth):
    """The ``APPEND`` command adds a new message to a mailbox.

    See Also:
        `RFC 3502 6.3.11.
        <https://tools.ietf.org/html/rfc3502#section-6.3.11>`_

    Args:
        tag: The command tag.
        mailbox: The mailbox name.
        messages: List of tuples containing the raw messages bytes, the
            flags, and the internal timestamp to assign to the message.

    """

    command = b'APPEND'

    def __init__(self, tag: bytes, mailbox: Mailbox,
                 messages: Sequence[_AppendMsgArg]) -> None:
        super().__init__(tag)
        self.mailbox_obj = mailbox
        self.messages: Sequence[AppendMessage] = \
            [AppendMessage(message, frozenset(flags),
                           when or datetime.now(), options)
             for message, flags, when, options in messages]

    @property
    def mailbox(self) -> str:
        return str(self.mailbox_obj)

    @classmethod
    def _parse_msg(cls, buf: bytes, params: Params) \
            -> Tuple['_AppendMsgArg', bytes]:
        _, buf = Space.parse(buf, params)
        try:
            params_copy = params.copy(list_expected=[Flag])
            flag_list, buf = ListP.parse(buf, params_copy)
        except UnexpectedType:
            raise
        except NotParseable:
            flags: Sequence[Flag] = []
        else:
            flags = flag_list.get_as(Flag)
            _, buf = Space.parse(buf, params)
        try:
            date_time_p, buf = DateTime.parse(buf, params)
        except InvalidContent:
            raise
        except NotParseable:
            date_time = None
        else:
            date_time = date_time_p.value
            _, buf = Space.parse(buf, params)
        options_list: List[ExtensionOption] = []
        while True:
            try:
                option, buf = ExtensionOption.parse(buf, params)
            except NotParseable:
                break
            else:
                options_list.append(option)
        options = ExtensionOptions(options_list)
        try:
            message, buf = LiteralString.parse(buf, params)
        except NotParseable as exc:
            if options:
                return (b'', flags, date_time, options), buf
            else:
                raise exc
        else:
            return (message.value, flags, date_time, options), buf

    @classmethod
    def parse(cls, buf: bytes, params: Params) \
            -> Tuple['AppendCommand', bytes]:
        _, buf = Space.parse(buf, params)
        mailbox, buf = Mailbox.parse(buf, params)
        first_msg, buf = cls._parse_msg(buf, params)
        messages = [first_msg]
        while True:
            try:
                next_msg, buf = cls._parse_msg(buf, params)
            except NotParseable:
                break
            else:
                messages.append(next_msg)
        _, buf = EndLine.parse(buf, params)
        return cls(params.tag, mailbox, messages), buf


class CreateCommand(CommandMailboxArg):
    """The ``CREATE`` command creates a new mailbox."""

    command = b'CREATE'

    def __init__(self, tag: bytes, mailbox: Mailbox,
                 options: ExtensionOptions) -> None:
        super().__init__(tag, mailbox)
        self.options = options

    @classmethod
    def parse(cls, buf: bytes, params: Params) \
            -> Tuple['CreateCommand', bytes]:
        _, buf = Space.parse(buf, params)
        mailbox, buf = Mailbox.parse(buf, params)
        options, buf = ExtensionOptions.parse(buf, params)
        _, buf = EndLine.parse(buf, params)
        return cls(params.tag, mailbox, options), buf


class DeleteCommand(CommandMailboxArg):
    """The ``DELETE`` command deletes a mailbox."""

    command = b'DELETE'


class ListCommand(CommandAuth):
    """The ``LIST`` command lists existing mailboxes.

    Args:
        tag: The command tag.
        ref_name: The mailbox reference name.
        filter_: The mailbox filter string.

    """

    command = b'LIST'

    _list_mailbox_pattern = re.compile(br'[\x21\x23-\x27\x2A-\x5B'
                                       br'\x5D-\x7A\x7C\x7E]+')

    def __init__(self, tag: bytes, ref_name: str, filter_: str) -> None:
        super().__init__(tag)
        self.ref_name = ref_name
        self.filter = filter_

    @classmethod
    def parse(cls, buf: bytes, params: Params) -> Tuple['ListCommand', bytes]:
        _, buf = Space.parse(buf, params)
        ref_name, buf = Mailbox.parse(buf, params)
        _, buf = Space.parse(buf, params)
        match = cls._list_mailbox_pattern.match(buf)
        if match:
            filter_raw = match.group(0)
            buf = buf[match.end(0):]
            filter_ = Mailbox.decode_name(filter_raw)
        else:
            filter_str, buf = String.parse(buf, params)
            filter_ = Mailbox.decode_name(filter_str.value)
        _, buf = EndLine.parse(buf, params)
        return cls(params.tag, ref_name.value, filter_), buf


class LSubCommand(ListCommand):
    """The ``LSUB`` command lists subscribed mailboxes."""

    command = b'LSUB'


class RenameCommand(CommandAuth):
    """The ``RENAME`` command renames an existing mailbox.

    Args:
        tag: The command tag.
        from_mailbox: The existing mailbox name.
        to_mailbox: The desired mailbox name.

    """

    command = b'RENAME'

    def __init__(self, tag: bytes, from_mailbox: Mailbox,
                 to_mailbox: Mailbox, options: ExtensionOptions) -> None:
        super().__init__(tag)
        self.from_mailbox_obj = from_mailbox
        self.to_mailbox_obj = to_mailbox
        self.options = options

    @property
    def from_mailbox(self) -> str:
        return str(self.from_mailbox_obj)

    @property
    def to_mailbox(self) -> str:
        return str(self.to_mailbox_obj)

    @classmethod
    def parse(cls, buf: bytes, params: Params) \
            -> Tuple['RenameCommand', bytes]:
        _, buf = Space.parse(buf, params)
        from_mailbox, buf = Mailbox.parse(buf, params)
        _, buf = Space.parse(buf, params)
        to_mailbox, buf = Mailbox.parse(buf, params)
        options, buf = ExtensionOptions.parse(buf, params)
        _, buf = EndLine.parse(buf, params)
        return cls(params.tag, from_mailbox, to_mailbox, options), buf


class SelectCommand(CommandMailboxArg):
    """The ``SELECT`` command selects a mailbox for querying, updates, and
    state changes.

    """

    command = b'SELECT'
    allow_updates = False

    def __init__(self, tag: bytes, mailbox: Mailbox,
                 options: ExtensionOptions) -> None:
        super().__init__(tag, mailbox)
        self.options = options

    @classmethod
    def parse(cls, buf: bytes, params: Params) \
            -> Tuple['SelectCommand', bytes]:
        _, buf = Space.parse(buf, params)
        mailbox, buf = Mailbox.parse(buf, params)
        options, buf = ExtensionOptions.parse(buf, params)
        _, buf = EndLine.parse(buf, params)
        return cls(params.tag, mailbox, options), buf


class ExamineCommand(SelectCommand):
    """The ``EXAMINE`` command selects a mailbox as read-only for querying and
    state changes.

    """

    command = b'EXAMINE'


class StatusCommand(CommandMailboxArg):
    """The ``STATUS`` command returns information about a mailbox without
    selecting it.

    Args:
        tag: The command tag.
        mailbox: The mailbox name.
        status_list: The status attributes to return.

    """

    command = b'STATUS'

    def __init__(self, tag: bytes, mailbox: Mailbox,
                 status_list: Sequence[StatusAttribute]) -> None:
        super().__init__(tag, mailbox)
        self.status_list = status_list

    @classmethod
    def parse(cls, buf: bytes, params: Params) \
            -> Tuple['StatusCommand', bytes]:
        _, buf = Space.parse(buf, params)
        mailbox, buf = Mailbox.parse(buf, params)
        _, buf = Space.parse(buf, params)
        params_copy = params.copy(list_expected=[StatusAttribute])
        status_list_p, after = ListP.parse(buf, params_copy)
        if not status_list_p.value:
            raise NotParseable(buf)
        _, buf = EndLine.parse(after, params)
        status_list = status_list_p.get_as(StatusAttribute)
        return cls(params.tag, mailbox, status_list), buf


class SubscribeCommand(CommandMailboxArg):
    """The ``SUBSCRIBE`` command subscribes to an existing mailbox."""

    command = b'SUBSCRIBE'


class UnsubscribeCommand(CommandMailboxArg):
    """The ``UNSUBSCRIBE`` command unsubscribes from a subscribed mailbox."""

    command = b'UNSUBSCRIBE'
