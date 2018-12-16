"""Base implementations of the :mod:`pymap.interfaces.message` interfaces."""

import re
from datetime import datetime
from typing import Any, Tuple, Iterable, Mapping, FrozenSet, \
    AbstractSet, Sequence, NamedTuple, TypeVar, Type
from typing_extensions import Final

from .flags import FlagOp, SessionFlags
from .interfaces.message import CachedMessage, MessageInterface
from .mime import MessageContent
from .parsing.response.fetch import EnvelopeStructure, BodyStructure, \
    MultipartBodyStructure, ContentBodyStructure, TextBodyStructure, \
    MessageBodyStructure
from .parsing.specials import Flag, ExtensionOptions

__all__ = ['AppendMessage', 'BaseMessage', 'MessageT']

#: Type variable with an upper bound of :class:`BaseMessage`.
MessageT = TypeVar('MessageT', bound='BaseMessage')


class _NoContent(ValueError):
    # Thrown when message contents are requested but the message object does
    # not have contents loaded.

    def __init__(self) -> None:
        super().__init__('Message content not available.')


class AppendMessage(NamedTuple):
    """A single message from the APPEND command.

    Args:
        message: The raw message bytes.
        flag_set: The flags to assign to the message.
        when: The internal timestamp to assign to the message.
        options: The extension options in use for the message.

    """

    message: bytes
    flag_set: FrozenSet[Flag]
    when: datetime
    options: ExtensionOptions


class BaseMessage(MessageInterface, CachedMessage):
    """Message metadata such as UID, permanent flags, and when the message
    was added to the system.

    Args:
        uid: The UID of the message.
        permanent_flags: Permanent flags for the message.
        internal_date: The internal date of the message.
        expunged: True if this message has been expunged from the mailbox.
        content: The content of the message.

    """

    __slots__ = ['uid', 'internal_date', 'expunged', '_permanent_flags',
                 '_flags_key', '_content', '_kwargs']

    def __init__(self, uid: int, permanent_flags: Iterable[Flag] = None,
                 internal_date: datetime = None, expunged: bool = False,
                 content: MessageContent = None, **kwargs: Any) -> None:
        super().__init__()
        self.uid: Final = uid
        self.internal_date: Final = internal_date
        self.expunged: Final = expunged
        self._permanent_flags = frozenset(permanent_flags or [])
        self._flags_key = (uid, self._permanent_flags)
        self._content = content
        self._kwargs = kwargs

    @classmethod
    def parse(cls: Type[MessageT], uid: int, data: bytes,
              permanent_flags: Iterable[Flag] = None,
              internal_date: datetime = None, expunged: bool = False,
              **kwargs: Any) -> MessageT:
        """Parse the given file object containing a MIME-encoded email message
        into a :class:`BaseLoadedMessage` object.

        Args:
            uid: The UID of the message.
            data: The raw contents of the message.
            permanent_flags: Permanent flags for the message.
            internal_date: The internal date of the message.
            expunged: True if this message has been expunged from the mailbox.

        """
        content = MessageContent.parse(data)
        return cls(uid, permanent_flags, internal_date, expunged,
                   content, **kwargs)

    @property
    def content(self) -> MessageContent:
        """The MIME-parsed message content."""
        if self._content is None:
            raise _NoContent()
        return self._content

    def copy(self: MessageT, new_uid: int) -> MessageT:
        cls = type(self)
        return cls(new_uid, self._permanent_flags, self.internal_date,
                   self.expunged, self._content, **self._kwargs)

    def get_flags(self, session_flags: SessionFlags = None) -> FrozenSet[Flag]:
        if session_flags:
            return self._permanent_flags | session_flags.get(self.uid)
        else:
            return self._permanent_flags

    def update_flags(self, flag_set: AbstractSet[Flag],
                     flag_op: FlagOp = FlagOp.REPLACE) -> None:
        new_flags = flag_op.apply(self._permanent_flags, flag_set)
        self._permanent_flags = new_flags
        self._flags_key = (self.uid, new_flags)

    @property
    def flags_key(self) -> Tuple[int, FrozenSet[Flag]]:
        return self._flags_key

    @classmethod
    def _get_subpart(cls: Type[MessageT], msg: MessageT, section) \
            -> MessageContent:
        if section:
            subpart = msg.content
            for i in section:
                if subpart.body.has_nested:
                    subpart = subpart.body.nested[i - 1]
                elif i == 1:
                    pass
                else:
                    raise IndexError(i)
            return subpart
        else:
            return msg.content

    def get_header(self, name: bytes) -> Sequence[str]:
        try:
            return self.content.header.parsed[name]
        except (KeyError, _NoContent):
            return []

    def get_headers(self, section: Iterable[int] = None,
                    subset: Iterable[bytes] = None,
                    inverse: bool = False) -> bytes:
        try:
            msg = self._get_subpart(self, section)
        except (IndexError, _NoContent):
            return b''
        return self._get_headers(msg, subset, inverse)

    @classmethod
    def _get_headers(cls, msg: MessageContent,
                     subset: Iterable[bytes] = None,
                     inverse: bool = False) -> bytes:
        ret = bytearray()
        for key, value in msg.header.folded:
            if subset is None or inverse != (key in subset):
                ret += value
        if ret:
            ret += b'\r\n'
        return bytes(ret)

    def get_body(self, section: Iterable[int] = None,
                 binary: bool = False) -> bytes:
        try:
            msg = self._get_subpart(self, section)
        except (IndexError, _NoContent):
            return b''
        return self._get_bytes(msg, binary)

    def get_text(self, section: Iterable[int] = None,
                 binary: bool = False) -> bytes:
        try:
            msg = self._get_subpart(self, section)
        except (IndexError, _NoContent):
            return b''
        return self._get_bytes(msg, binary, True)

    @classmethod
    def _get_bytes(cls, msg: MessageContent, binary: bool = False,
                   body_only: bool = False) -> bytes:
        if body_only:
            return bytes(msg.body.raw)
        else:
            return bytes(msg.raw)

    @classmethod
    def _get_size(cls, msg: MessageContent, binary: bool = False) -> int:
        return len(msg.raw)

    @classmethod
    def _get_size_with_lines(cls, msg: MessageContent) -> Tuple[int, int]:
        return len(msg.raw), msg.lines

    def get_size(self, section: Iterable[int] = None,
                 binary: bool = False) -> int:
        try:
            msg = self._get_subpart(self, section)
        except (IndexError, _NoContent):
            return 0
        return self._get_size(msg, binary)

    def get_envelope_structure(self) -> EnvelopeStructure:
        try:
            return self._get_envelope_structure(self.content)
        except _NoContent:
            return EnvelopeStructure.empty()

    def get_body_structure(self) -> BodyStructure:
        try:
            return self._get_body_structure(self.content)
        except _NoContent:
            return BodyStructure.empty()

    @classmethod
    def _get_envelope_structure(cls, msg: MessageContent) -> EnvelopeStructure:
        parsed = msg.header.parsed
        return EnvelopeStructure(
            parsed.date, parsed.subject, parsed.from_, parsed.sender,
            parsed.reply_to, parsed.to, parsed.cc, parsed.bcc,
            parsed.in_reply_to, parsed.message_id)

    @classmethod
    def _get_params(cls, msg: MessageContent) -> Mapping[str, Any]:
        return msg.body.content_type.params

    @classmethod
    def _get_body_structure(cls, msg: MessageContent) -> BodyStructure:
        parsed = msg.header.parsed
        maintype = msg.body.content_type.maintype
        subtype = msg.body.content_type.subtype
        params = cls._get_params(msg)
        disposition = parsed.content_disposition
        language = parsed.content_language
        location = parsed.content_location
        if maintype == 'multipart':
            sub_body_structs = [cls._get_body_structure(part)
                                for part in msg.body.nested]
            return MultipartBodyStructure(
                subtype, params, disposition, language, location,
                sub_body_structs)
        content_id = parsed.content_id
        content_desc = parsed.content_description
        content_encoding = parsed.content_transfer_encoding
        if maintype == 'message' and subtype == 'rfc822':
            sub_msg = msg.body.nested[0]
            sub_env_struct = cls._get_envelope_structure(sub_msg)
            sub_body_struct = cls._get_body_structure(sub_msg)
            size, lines = cls._get_size_with_lines(msg)
            return MessageBodyStructure(
                params, disposition, language, location, content_id,
                content_desc, content_encoding, None, size, lines,
                sub_env_struct, sub_body_struct)
        elif maintype == 'text':
            size, lines = cls._get_size_with_lines(msg)
            return TextBodyStructure(
                subtype, params, disposition, language, location,
                content_id, content_desc, content_encoding, None, size, lines)
        size = cls._get_size(msg, True)
        return ContentBodyStructure(
            maintype, subtype, params, disposition, language, location,
            content_id, content_desc, content_encoding, None, size)

    def contains(self, value: bytes) -> bool:
        if self._content is None:
            return False
        pattern = re.compile(re.escape(value), re.I)
        for part in self._content.walk():
            headers = self._get_headers(part)
            if pattern.search(headers) is not None:
                return True
            elif part.body.content_type.maintype == 'text':
                data = self._get_bytes(part, True, True)
                if pattern.search(data) is not None:
                    return True
        return False
