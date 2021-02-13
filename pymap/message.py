"""Base implementations of the :mod:`pymap.interfaces.message` interfaces."""

from __future__ import annotations

import re
from abc import ABCMeta
from collections.abc import Collection, Iterable, Mapping, Sequence
from datetime import datetime
from typing import Any, Optional, Final

from .bytes import Writeable
from .flags import SessionFlags
from .interfaces.message import FlagsKey, CachedMessage, MessageInterface, \
    LoadedMessageInterface
from .mime import MessageContent
from .mime.cte import MessageDecoder
from .parsing.response.fetch import EnvelopeStructure, BodyStructure, \
    MultipartBodyStructure, ContentBodyStructure, TextBodyStructure, \
    MessageBodyStructure
from .parsing.specials import Flag, ObjectId, FetchRequirement

__all__ = ['BaseMessage', 'BaseLoadedMessage']


class _NoContent(ValueError):
    # Thrown when message contents were requested, but the backend did not or
    # could not load them.

    def __init__(self) -> None:
        super().__init__('Message content not available.')


class BaseMessage(MessageInterface, CachedMessage, metaclass=ABCMeta):
    """Message metadata such as UID, permanent flags, and when the message
    was added to the system.

    Args:
        uid: The UID of the message.
        internal_date: The internal date of the message.
        permanent_flags: Permanent flags for the message.
        email_id: The message content identifier for the message.
        thread_id: The thread identifier for the message.
        expunged: True if this message has been expunged from the mailbox.

    """

    __slots__ = ['uid', 'internal_date', 'expunged', '_permanent_flags',
                 '_email_id', '_thread_id', '_flags_key']

    def __init__(self, uid: int, internal_date: datetime,
                 permanent_flags: Iterable[Flag], *,
                 email_id: ObjectId = None, thread_id: ObjectId = None,
                 expunged: bool = False) -> None:
        super().__init__()
        self.uid: Final = uid
        self.internal_date: Final = internal_date
        self.expunged: Final = expunged
        self._email_id = email_id or ObjectId(None)
        self._thread_id = thread_id or ObjectId(None)
        self._permanent_flags = frozenset(permanent_flags or ())
        self._flags_key = (uid, self._permanent_flags)

    @property
    def email_id(self) -> ObjectId:
        return self._email_id

    @property
    def thread_id(self) -> ObjectId:
        return self._thread_id

    @property
    def permanent_flags(self) -> frozenset[Flag]:
        return self._permanent_flags

    @permanent_flags.setter
    def permanent_flags(self, permanent_flags: frozenset[Flag]) -> None:
        self._permanent_flags = permanent_flags
        self._flags_key = (self.uid, permanent_flags)

    def get_flags(self, session_flags: SessionFlags) -> frozenset[Flag]:
        msg_sflags = session_flags.get(self.uid)
        if msg_sflags:
            return self._permanent_flags | msg_sflags
        else:
            return self._permanent_flags

    @property
    def flags_key(self) -> FlagsKey:
        return self._flags_key

    def __repr__(self) -> str:
        type_name = type(self).__name__
        return f'<{type_name} uid={self.uid} flags={self.permanent_flags}>'


class BaseLoadedMessage(LoadedMessageInterface, metaclass=ABCMeta):
    """The loaded message content, implemented using an instance of
    :class:`~pymap.mime.MessageContent`.

    Args:
        message: The message object.
        requirement: The fetch requirement of the loaded content.
        content: The MIME-parsed message content, if available.

    """

    __slots__ = ['_message', '_requirement', '_content']

    def __init__(self, message: MessageInterface,
                 requirement: FetchRequirement,
                 content: Optional[MessageContent]) -> None:
        super().__init__()
        self._message = message
        self._requirement = requirement
        self._content = content

    @property
    def message(self) -> MessageInterface:
        return self._message

    @property
    def requirement(self) -> FetchRequirement:
        return self._requirement

    @property
    def content(self) -> MessageContent:
        if self._content is None:
            raise _NoContent()
        return self._content

    def __bytes__(self) -> bytes:
        return bytes(self.content)

    def _get_subpart(self, section) -> MessageContent:
        if section:
            subpart = self.content
            for i in section:
                if subpart.body.has_nested:
                    subpart = subpart.body.nested[i - 1]
                elif i == 1:
                    pass
                else:
                    raise IndexError(i)
            return subpart
        else:
            return self.content

    def get_header(self, name: bytes) -> Sequence[str]:
        try:
            return self.content.header.parsed[name]
        except (KeyError, _NoContent):
            return []

    def get_headers(self, section: Sequence[int]) -> Writeable:
        try:
            msg = self._get_subpart(section)
        except (IndexError, _NoContent):
            return Writeable.empty()
        else:
            return msg.header

    def get_body(self, section: Sequence[int] = None,
                 binary: bool = False) -> Writeable:
        try:
            msg = self._get_subpart(section)
        except (IndexError, _NoContent):
            return Writeable.empty()
        if binary:
            decoded = MessageDecoder.of(msg.header).decode(msg.body)
            if not section:
                return Writeable.concat((msg.header, decoded))
            else:
                return decoded
        else:
            if not section:
                return msg
            else:
                return msg.body

    def get_message_headers(self, section: Sequence[int] = None,
                            subset: Collection[bytes] = None,
                            inverse: bool = False) -> Writeable:
        try:
            msg = self._get_subpart(section)
        except (IndexError, _NoContent):
            return Writeable.empty()
        if section:
            if msg.is_rfc822:
                msg = msg.body.nested[0]
            else:
                return Writeable.empty()
        if subset is None:
            return msg.header
        headers = Writeable.concat(value for key, value in msg.header.folded
                                   if inverse != (key.upper() in subset))
        return Writeable.concat((headers, Writeable.wrap(b'\r\n')))

    def get_message_text(self, section: Sequence[int] = None) -> Writeable:
        try:
            msg = self._get_subpart(section)
        except (IndexError, _NoContent):
            return Writeable.empty()
        if section:
            if msg.is_rfc822:
                msg = msg.body.nested[0]
            else:
                return Writeable.empty()
        return msg.body

    @classmethod
    def _get_size_with_lines(cls, msg: MessageContent) -> tuple[int, int]:
        return len(msg), msg.lines

    def get_size(self, section: Sequence[int] = None) -> int:
        try:
            msg = self._get_subpart(section)
        except (IndexError, _NoContent):
            return 0
        return len(msg)

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
        size = len(msg)
        return ContentBodyStructure(
            maintype, subtype, params, disposition, language, location,
            content_id, content_desc, content_encoding, None, size)

    def contains(self, value: bytes) -> bool:
        try:
            content = self.content
        except _NoContent:
            return False
        pattern = re.compile(re.escape(value), re.I)
        for part in content.walk():
            if pattern.search(bytes(part.header)) is not None:
                return True
            elif part.body.content_type.maintype == 'text':
                if pattern.search(bytes(part.body)) is not None:
                    return True
        return False
