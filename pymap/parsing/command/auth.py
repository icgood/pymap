
from __future__ import annotations

from abc import ABCMeta
from collections.abc import Iterable, Sequence
from typing import ClassVar, Optional

from . import CommandAuth
from .. import Space, EndLine, Params
from ..exceptions import NotParseable, UnexpectedType, InvalidContent
from ..message import AppendMessage
from ..modutf7 import modutf7_decode
from ..primitives import List, String, LiteralString
from ..specials import Mailbox, DateTime, Flag, StatusAttribute, \
    ExtensionOption, ExtensionOptions
from ...bytes import rev

__all__ = ['AppendCommand', 'CreateCommand', 'DeleteCommand', 'ExamineCommand',
           'ListCommand', 'LSubCommand', 'RenameCommand', 'SelectCommand',
           'StatusCommand', 'SubscribeCommand', 'UnsubscribeCommand']


class CommandMailboxArg(CommandAuth, metaclass=ABCMeta):

    def __init__(self, tag: bytes, mailbox: Mailbox) -> None:
        super().__init__(tag)
        self.mailbox_obj = mailbox

    @property
    def mailbox(self) -> str:
        return str(self.mailbox_obj)

    @classmethod
    def parse(cls, buf: memoryview, params: Params) \
            -> tuple[CommandMailboxArg, memoryview]:
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
        cancelled: True if the append command was cancelled.

    """

    command = b'APPEND'

    def __init__(self, tag: bytes, mailbox: Mailbox,
                 messages: Iterable[AppendMessage],
                 cancelled: bool = False, error: Exception = None) -> None:
        super().__init__(tag)
        self.mailbox_obj = mailbox
        self.messages: Sequence[AppendMessage] = list(messages)
        self.cancelled = cancelled
        self.error = error

    @property
    def mailbox(self) -> str:
        return str(self.mailbox_obj)

    @classmethod
    def _parse_msg(cls, name: str, buf: memoryview, params: Params) \
            -> tuple[Optional[AppendMessage], memoryview]:
        _, buf = Space.parse(buf, params)
        try:
            params_copy = params.copy(list_expected=[Flag])
            flag_list, buf = List.parse(buf, params_copy)
        except UnexpectedType:
            raise
        except NotParseable:
            flags: frozenset[Flag] = frozenset()
        else:
            flags = frozenset(flag_list.get_as(Flag))
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
        options_list: list[ExtensionOption] = []
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
                literal = b''
            else:
                raise exc
        else:
            literal = message.value
            if literal == b'':
                return None, buf
        append_msg = AppendMessage(literal, date_time, flags, options)
        return append_msg, buf

    @classmethod
    def parse(cls, buf: memoryview, params: Params) \
            -> tuple[AppendCommand, memoryview]:
        _, buf = Space.parse(buf, params)
        mailbox, buf = Mailbox.parse(buf, params)
        messages: list[AppendMessage] = []
        error: Optional[Exception] = None
        cancelled = False
        while True:
            try:
                next_msg, buf = cls._parse_msg(mailbox.value, buf, params)
            except NotParseable:
                if not messages:
                    raise
                break
            else:
                if next_msg is None:
                    cancelled = True
                    break
                messages.append(next_msg)
        _, buf = EndLine.parse(buf, params)
        return cls(params.tag, mailbox, messages, cancelled, error), buf


class CreateCommand(CommandMailboxArg):
    """The ``CREATE`` command creates a new mailbox."""

    command = b'CREATE'

    def __init__(self, tag: bytes, mailbox: Mailbox,
                 options: ExtensionOptions) -> None:
        super().__init__(tag, mailbox)
        self.options = options

    @classmethod
    def parse(cls, buf: memoryview, params: Params) \
            -> tuple[CreateCommand, memoryview]:
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

    #: All mailboxes may be listed, not only subscribed mailboxes.
    only_subscribed: ClassVar[bool] = False

    _list_mailbox_pattern = rev.compile(br'[\x21\x23-\x27\x2A-\x5B'
                                        br'\x5D-\x7A\x7C\x7E]+')

    def __init__(self, tag: bytes, ref_name: str, filter_: str) -> None:
        super().__init__(tag)
        self.ref_name = ref_name
        self.filter = filter_

    @classmethod
    def parse(cls, buf: memoryview, params: Params) \
            -> tuple[ListCommand, memoryview]:
        _, buf = Space.parse(buf, params)
        ref_name, buf = Mailbox.parse(buf, params)
        _, buf = Space.parse(buf, params)
        match = cls._list_mailbox_pattern.match(buf)
        if match:
            filter_raw = match.group(0)
            buf = buf[match.end(0):]
            filter_ = modutf7_decode(filter_raw)
        else:
            filter_str, buf = String.parse(buf, params)
            filter_ = modutf7_decode(filter_str.value)
        _, buf = EndLine.parse(buf, params)
        return cls(params.tag, ref_name.value, filter_), buf


class LSubCommand(ListCommand):
    """The ``LSUB`` command lists subscribed mailboxes."""

    command = b'LSUB'
    delegate = ListCommand

    #: Only subscribed mailboxes may be listed.
    only_subscribed: ClassVar[bool] = True


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
    def parse(cls, buf: memoryview, params: Params) \
            -> tuple[RenameCommand, memoryview]:
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

    #: The mailbox will not be opened read-only unless the backend indicates
    #: that it must be.
    readonly: ClassVar[bool] = False

    def __init__(self, tag: bytes, mailbox: Mailbox,
                 options: ExtensionOptions) -> None:
        super().__init__(tag, mailbox)
        self.options = options

    @classmethod
    def parse(cls, buf: memoryview, params: Params) \
            -> tuple[SelectCommand, memoryview]:
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
    delegate = SelectCommand

    #: The mailbox will be opened read-only.
    readonly: ClassVar[bool] = True


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
    def parse(cls, buf: memoryview, params: Params) \
            -> tuple[StatusCommand, memoryview]:
        _, buf = Space.parse(buf, params)
        mailbox, buf = Mailbox.parse(buf, params)
        _, buf = Space.parse(buf, params)
        params_copy = params.copy(list_expected=[StatusAttribute])
        status_list_p, after = List.parse(buf, params_copy)
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
