"""Base implementations of the :mod:`pymap.interfaces.message` interfaces."""

from datetime import datetime
from email.generator import BytesGenerator
from email.message import EmailMessage
from email.parser import BytesParser
from email.policy import SMTP
from io import BytesIO
from typing import Any, Tuple, Optional, Iterable, Set, Dict, FrozenSet, \
    Sequence, List, NamedTuple, BinaryIO, TypeVar, Type

from .flags import FlagOp, SessionFlags
from .interfaces.message import Header, MessageInterface
from .parsing.response.fetch import EnvelopeStructure, BodyStructure, \
    MultipartBodyStructure, ContentBodyStructure, TextBodyStructure, \
    MessageBodyStructure
from .parsing.specials import ExtensionOptions
from .parsing.specials.flag import Flag, Deleted

__all__ = ['AppendMessage', 'BaseMessage', 'MessageT', 'Policy', 'Policy7Bit']

#: Type variable with an upper bound of :class:`BaseMessage`.
MessageT = TypeVar('MessageT', bound='BaseMessage')

#: :class:`~email.policy.Policy` used for 8-bit serialization.
Policy = SMTP.clone(cte_type='8bit', utf8=True)

#: :class:`~email.policy.Policy` used for 7-bit serialization.
Policy7Bit = Policy.clone(cte_type='7bit')


class AppendMessage(NamedTuple):
    """A single message from the APPEND command.

    Attributes:
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


class BaseMessage(MessageInterface):
    """Message metadata such as UID, permanent flags, and when the message
    was added to the system.

    Args:
        uid: The UID of the message.
        permanent_flags: Permanent flags for the message.
        internal_date: The internal date of the message.
        expunged: True if this message has been expunged from the mailbox.
        contents: The contents of the message.

    """

    __slots__ = ['_uid', '_permanent_flags', '_internal_date',
                 '_expunged', '_contents', '_kwargs']

    def __init__(self, uid: int, permanent_flags: Iterable[Flag] = None,
                 internal_date: datetime = None, expunged: bool = False,
                 contents: EmailMessage = None, **kwargs: Any) -> None:
        super().__init__()
        self._uid = uid
        self._permanent_flags = set(permanent_flags or [])
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
    def permanent_flags(self) -> Set[Flag]:
        return self._permanent_flags

    @property
    def internal_date(self) -> Optional[datetime]:
        return self._internal_date

    @property
    def contents(self) -> EmailMessage:
        """The MIME-parsed message object."""
        if self._contents is None:
            raise ValueError('Message contents not available.')
        return self._contents

    def copy(self: MessageT, new_uid: int) -> MessageT:
        cls = type(self)
        return cls(new_uid, self.permanent_flags, self.internal_date,
                   self.expunged, self._contents, **self._kwargs)

    def get_flags(self, session_flags: SessionFlags = None) -> FrozenSet[Flag]:
        if self.expunged:
            return frozenset({Deleted})
        elif session_flags:
            return frozenset(self.permanent_flags | session_flags[self.uid])
        else:
            return frozenset(self.permanent_flags)

    def update_flags(self, flag_set: Iterable[Flag],
                     flag_op: FlagOp = FlagOp.REPLACE) -> FrozenSet[Flag]:
        new_flags = flag_op.apply(self.permanent_flags, flag_set)
        self.permanent_flags.clear()
        self.permanent_flags.update(new_flags)
        return new_flags

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
        return self.contents.get_all(name, [])

    def get_headers(self, section: Iterable[int] = None,
                    subset: Iterable[str] = None,
                    inverse: bool = False) \
            -> Optional[bytes]:
        try:
            msg = self._get_subpart(self, section)
        except IndexError:
            return None
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
            return None

    def get_body(self, section: Iterable[int] = None,
                 binary: bool = False) -> Optional[bytes]:
        try:
            msg = self._get_subpart(self, section)
        except IndexError:
            return None
        return self._get_bytes(msg, binary)

    def get_text(self, section: Iterable[int] = None,
                 binary: bool = False) -> Optional[bytes]:
        try:
            msg = self._get_subpart(self, section)
        except IndexError:
            return None
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
        except IndexError:
            return 0
        return self._get_size(msg, binary)

    def get_envelope_structure(self) -> EnvelopeStructure:
        return self._get_envelope_structure(self.contents)

    def get_body_structure(self) -> BodyStructure:
        return self._get_body_structure(self.contents)

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
