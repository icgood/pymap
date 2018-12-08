"""Base implementations of the :mod:`pymap.interfaces.message` interfaces."""

import re
from datetime import datetime
from email.generator import BytesGenerator
from email.message import EmailMessage
from email.parser import BytesParser
from email.policy import SMTP
from io import BytesIO
from typing import cast, Any, Tuple, Optional, Iterable, Dict, FrozenSet, \
    AbstractSet, Sequence, List, NamedTuple, BinaryIO, TypeVar, Type

from .flags import FlagOp, SessionFlags
from .interfaces.message import Header, CachedMessage, MessageInterface
from .parsing.response.fetch import EnvelopeStructure, BodyStructure, \
    MultipartBodyStructure, ContentBodyStructure, TextBodyStructure, \
    MessageBodyStructure
from .parsing.specials import Flag, ExtensionOptions

__all__ = ['AppendMessage', 'BaseMessage', 'MessageT', 'Policy', 'Policy7Bit']

#: Type variable with an upper bound of :class:`BaseMessage`.
MessageT = TypeVar('MessageT', bound='BaseMessage')

#: :class:`~email.policy.Policy` used for 8-bit serialization.
Policy = SMTP.clone(cte_type='8bit', utf8=True)

#: :class:`~email.policy.Policy` used for 7-bit serialization.
Policy7Bit = Policy.clone(cte_type='7bit')


class _NoContents(ValueError):
    # Thrown when message contents are requested but the message object does
    # not have contents loaded.

    def __init__(self) -> None:
        super().__init__('Message contents not available.')


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


class _BodyOnlyBytesGenerator(BytesGenerator):
    # This should produce a bytestring of a email.message.Message object
    # without including any headers, by exploiting the internal _write_headers
    # method.

    def _write_headers(self, *args, **kwargs):
        pass


class BaseMessage(MessageInterface, CachedMessage):
    """Message metadata such as UID, permanent flags, and when the message
    was added to the system.

    Args:
        uid: The UID of the message.
        permanent_flags: Permanent flags for the message.
        internal_date: The internal date of the message.
        expunged: True if this message has been expunged from the mailbox.
        contents: The contents of the message.

    """

    __slots__ = ['_uid', '_permanent_flags', '_internal_date', '_expunged',
                 '_metadata_hash', '_contents', '_kwargs']

    def __init__(self, uid: int, permanent_flags: Iterable[Flag] = None,
                 internal_date: datetime = None, expunged: bool = False,
                 contents: EmailMessage = None, **kwargs: Any) -> None:
        super().__init__()
        self._uid = uid
        self._permanent_flags = frozenset(permanent_flags or [])
        self._internal_date = internal_date
        self._expunged = expunged
        self._contents = contents
        self._kwargs = kwargs

    @classmethod
    def parse(cls: Type[MessageT], uid: int, data: BinaryIO,
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
        contents = BytesParser(policy=Policy).parse(data)
        if not isinstance(contents, EmailMessage):
            raise TypeError(contents)
        return cls(uid, permanent_flags, internal_date, expunged,
                   contents, **kwargs)

    @property
    def uid(self) -> int:
        return self._uid

    @property
    def expunged(self) -> bool:
        return self._expunged

    @property
    def internal_date(self) -> Optional[datetime]:
        return self._internal_date

    @property
    def contents(self) -> EmailMessage:
        """The MIME-parsed message object."""
        if self._contents is None:
            raise _NoContents()
        return self._contents

    def copy(self: MessageT, new_uid: int) -> MessageT:
        cls = type(self)
        return cls(new_uid, self._permanent_flags, self.internal_date,
                   self.expunged, self._contents, **self._kwargs)

    def get_flags(self, session_flags: SessionFlags = None) -> FrozenSet[Flag]:
        if session_flags:
            return self._permanent_flags | session_flags.get(self.uid)
        else:
            return self._permanent_flags

    def update_flags(self, flag_set: AbstractSet[Flag],
                     flag_op: FlagOp = FlagOp.REPLACE) -> None:
        self._permanent_flags = flag_op.apply(self._permanent_flags, flag_set)

    @classmethod
    def _get_subpart(cls: Type[MessageT], msg: MessageT, section) \
            -> 'EmailMessage':
        if section:
            subpart = msg.contents
            for i in section:
                if subpart.is_multipart():
                    subpart = subpart.get_payload(i - 1)  # type: ignore
                elif i == 1:
                    pass
                else:
                    raise IndexError(i)
            return subpart
        else:
            return msg.contents

    def get_header(self, name: str) -> Sequence[Header]:
        try:
            return self.contents.get_all(name, [])
        except _NoContents:
            return []

    def get_headers(self, section: Iterable[int] = None,
                    subset: Iterable[str] = None,
                    inverse: bool = False) -> bytes:
        try:
            msg = self._get_subpart(self, section)
        except (IndexError, _NoContents):
            return b''
        return self._get_headers(msg, subset, inverse)

    @classmethod
    def _get_headers(cls, msg: EmailMessage,
                     subset: Iterable[str] = None,
                     inverse: bool = False) -> bytes:
        ret: List[bytes] = []
        for key, value in msg.items():
            if subset is not None:
                if inverse != (key in subset):
                    ret.append(Policy.fold_binary(key, str(value)))
            else:
                ret.append(Policy.fold_binary(key, str(value)))
        if len(ret) > 0:
            linesep = Policy.linesep.encode('ascii')
            return b''.join(ret) + linesep
        else:
            return b''

    def get_body(self, section: Iterable[int] = None,
                 binary: bool = False) -> bytes:
        try:
            msg = self._get_subpart(self, section)
        except (IndexError, _NoContents):
            return b''
        return self._get_bytes(msg, binary)

    def get_text(self, section: Iterable[int] = None,
                 binary: bool = False) -> bytes:
        try:
            msg = self._get_subpart(self, section)
        except (IndexError, _NoContents):
            return b''
        return self._get_bytes(msg, binary, True)

    @classmethod
    def _get_bytes(cls, msg: 'EmailMessage', binary: bool = False,
                   body_only: bool = False) -> bytes:
        ofp = BytesIO()
        generator: Type[BytesGenerator] = _BodyOnlyBytesGenerator \
            if body_only else BytesGenerator
        policy = Policy if binary else Policy7Bit
        try:
            generator(ofp, policy=policy).flatten(msg)  # type: ignore
        except (LookupError, UnicodeEncodeError):
            # Message had a malformed or incorrect charset, default to binary.
            return cls._get_bytes(msg, True, body_only)
        return ofp.getvalue()

    @classmethod
    def _get_size(cls, msg: 'EmailMessage', binary: bool = False) -> int:
        data = cls._get_bytes(msg, binary)
        size = len(data)
        return size

    @classmethod
    def _get_size_with_lines(cls, msg: 'EmailMessage') -> Tuple[int, int]:
        data = cls._get_bytes(msg, True)
        size = len(data)
        lines = data.count(b'\n')
        return size, lines

    def get_size(self, section: Iterable[int] = None,
                 binary: bool = False) -> int:
        try:
            msg = self._get_subpart(self, section)
        except (IndexError, _NoContents):
            return 0
        return self._get_size(msg, binary)

    def get_envelope_structure(self) -> EnvelopeStructure:
        try:
            return self._get_envelope_structure(self.contents)
        except _NoContents:
            return EnvelopeStructure.empty()

    def get_body_structure(self) -> BodyStructure:
        try:
            return self._get_body_structure(self.contents)
        except _NoContents:
            return BodyStructure.empty()

    @classmethod
    def _get_envelope_structure(cls, msg: EmailMessage) -> EnvelopeStructure:
        return EnvelopeStructure(  # type: ignore
            msg.get('Date'),
            msg.get('Subject'),
            msg.get_all('From'),
            msg.get_all('Sender'),
            msg.get_all('Reply-To'),
            msg.get_all('To'),
            msg.get_all('Cc'),
            msg.get_all('Bcc'),
            msg.get('In-Reply-To'),
            msg.get('Message-Id'))

    @classmethod
    def _get_params(cls, msg: EmailMessage) -> Dict[str, str]:
        content_type = msg.get('Content-Type')
        if content_type:
            return content_type.params  # type: ignore
        else:
            return {}

    @classmethod
    def _get_body_structure(cls, msg: EmailMessage) -> BodyStructure:
        maintype = msg.get_content_maintype()
        subtype = msg.get_content_subtype()
        params = cls._get_params(msg)
        disposition = msg.get('Content-Disposition')
        language = msg.get('Content-Language')
        location = msg.get('Content-Location')
        if msg.is_multipart():
            sub_body_structs = [cls._get_body_structure(part)  # type: ignore
                                for part in msg.get_payload()]  # type: ignore
            return MultipartBodyStructure(  # type: ignore
                subtype, params, disposition, language, location,
                sub_body_structs)
        content_id = msg.get('Content-Id')
        content_desc = msg.get('Content-Description')
        content_encoding = msg.get('Content-Transfer-Encoding')
        if maintype == 'message' and subtype == 'rfc822':
            sub_msg = msg.get_payload(0)
            if not isinstance(sub_msg, EmailMessage):
                raise TypeError(sub_msg)
            sub_env_struct = cls._get_envelope_structure(sub_msg)
            sub_body_struct = cls._get_body_structure(sub_msg)
            size, lines = cls._get_size_with_lines(msg)
            return MessageBodyStructure(  # type: ignore
                params, disposition, language, location, content_id,
                content_desc, content_encoding, None, size, lines,
                sub_env_struct, sub_body_struct)
        elif maintype == 'text':
            size, lines = cls._get_size_with_lines(msg)
            return TextBodyStructure(  # type: ignore
                subtype, params, disposition, language, location,
                content_id, content_desc, content_encoding, None, size, lines)
        size = cls._get_size(msg, True)
        return ContentBodyStructure(  # type: ignore
            maintype, subtype, params, disposition, language, location,
            content_id, content_desc, content_encoding, None, size)

    def contains(self, value: bytes) -> bool:
        if self._contents is None:
            return False
        pattern = re.compile(re.escape(value), re.I)
        for part in self._contents.walk():
            msg = cast(EmailMessage, part)
            headers = self._get_headers(msg)
            if pattern.search(headers) is not None:
                return True
            if msg.get_content_maintype() == 'text':
                data = self._get_bytes(msg, True, True)
                if pattern.search(data) is not None:
                    return True
        return False
