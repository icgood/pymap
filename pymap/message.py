"""Base implementations of the :mod:`pymap.interfaces.message` interfaces."""

import io
from datetime import datetime
from email.generator import BytesGenerator
from email.headerregistry import BaseHeader
from email.message import EmailMessage
from email.policy import SMTP
from typing import cast, Tuple, Optional, Iterable, Set, Dict, FrozenSet, \
    Sequence, Union

from .interfaces.message import Message, LoadedMessage
from .parsing.response.fetch import EnvelopeStructure, BodyStructure, \
    MultipartBodyStructure, ContentBodyStructure, TextBodyStructure, \
    MessageBodyStructure
from .parsing.specials import Flag
from .selected import SelectedMailbox

__all__ = ['BaseMessage', 'BaseLoadedMessage']


class _FullBytesGenerator(BytesGenerator):

    def __init__(self, ofp, binary):
        policy = SMTP if binary else SMTP.clone(cte_type='7bit')
        super().__init__(ofp, False, policy=policy)


class _BodyOnlyBytesGenerator(BytesGenerator):
    # This should produce a bytestring of a email.message.Message object
    # without including any headers, by exploiting the internal _write_headers
    # method.

    def __init__(self, ofp, binary):
        policy = SMTP if binary else SMTP.clone(cte_type='7bit')
        super().__init__(ofp, False, policy=policy)

    def _write_headers(self, *args, **kwargs):
        pass


class BaseMessage(Message):
    """Message metadata such as UID, permanent flags, and when the message
    was added to the system.

    Args:
        uid: The UID of the message.
        permanent_flags: Permanent flags for the message.
        internal_date: The internal date of the message.

    """

    def __init__(self, uid: int, permanent_flags: Iterable[Flag] = None,
                 internal_date: Optional[datetime] = None) -> None:
        super().__init__()
        self._uid = uid
        self._permanent_flags = set(permanent_flags or [])
        self._internal_date = internal_date

    @property
    def uid(self) -> int:
        return self._uid

    @property
    def permanent_flags(self) -> Set[Flag]:
        return self._permanent_flags

    @property
    def internal_date(self) -> Optional[datetime]:
        return self._internal_date

    def get_flags(self, session: Optional[SelectedMailbox]) \
            -> FrozenSet[Flag]:
        if session:
            session_flags = session.session_flags.get(self.uid)
            return frozenset(self.permanent_flags | session_flags)
        else:
            return frozenset(self.permanent_flags)


class BaseLoadedMessage(BaseMessage, LoadedMessage):
    """A message with its contents loaded, such that it pulls the information
    from a message object necessary to gather `message attributes
    <https://tools.ietf.org/html/rfc3501#section-2.3>`_, as needed by the
    `FETCH responses <https://tools.ietf.org/html/rfc3501#section-7.4.2>`_.

    Args:
        uid: The UID of the message.
        contents: The contents of the message.
        permanent_flags: Permanent flags for the message.
        internal_date: The internal date of the message.

    Attributes:
        contents: The MIME-parsed message object.

    """

    def __init__(self, uid: int, contents: EmailMessage,
                 permanent_flags: Iterable[Flag] = None,
                 internal_date: Optional[datetime] = None) -> None:
        super().__init__(uid, permanent_flags, internal_date)
        self.contents: EmailMessage = contents

    @classmethod
    def _get_subpart(cls, msg: 'BaseLoadedMessage', section) -> 'EmailMessage':
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

    def get_header(self, name: bytes) -> Sequence[Union[str, BaseHeader]]:
        name_str = str(name, 'ascii', 'ignore')
        values = self.contents.get_all(name_str, [])
        return cast(Sequence[Union[str, BaseHeader]], values)

    def get_headers(self, section: Optional[Iterable[int]] = None,
                    subset: Iterable[bytes] = None,
                    inverse: bool = False) \
            -> Optional[bytes]:
        try:
            msg = self._get_subpart(self, section)
        except IndexError:
            return None
        ret = EmailMessage(SMTP)
        for key, value in msg.items():
            if subset is not None:
                try:
                    key_bytes = bytes(key, 'ascii').upper()
                except UnicodeEncodeError:
                    pass
                else:
                    if inverse != (key_bytes in subset):
                        ret[key] = value
            else:
                ret[key] = value
        if len(ret) > 0:
            return bytes(ret)
        else:
            return None

    def get_body(self, section: Optional[Iterable[int]] = None,
                 binary: bool = False) -> Optional[bytes]:
        try:
            msg = self._get_subpart(self, section)
        except IndexError:
            return None
        return self._get_bytes(msg, binary)

    def get_text(self, section: Optional[Iterable[int]] = None,
                 binary: bool = False) -> Optional[bytes]:
        try:
            msg = self._get_subpart(self, section)
        except IndexError:
            return None
        ofp = io.BytesIO()
        _BodyOnlyBytesGenerator(ofp, binary).flatten(msg)
        return ofp.getvalue()

    @classmethod
    def _get_bytes(cls, msg: 'EmailMessage', binary: bool = False) -> bytes:
        ofp = io.BytesIO()
        _FullBytesGenerator(ofp, binary).flatten(msg)
        return ofp.getvalue()

    @classmethod
    def _get_size(cls, msg: 'EmailMessage', binary: bool = False) -> int:
        data = cls._get_bytes(msg, binary)
        size = len(data)
        return size

    @classmethod
    def _get_size_with_lines(cls, msg: 'EmailMessage') -> Tuple[int, int]:
        data = cls._get_bytes(msg)
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
            sub_msg = cast(EmailMessage, msg.get_payload(0))
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
        size = cls._get_size(msg)
        return ContentBodyStructure(  # type: ignore
            maintype, subtype, params, disposition, language, location,
            content_id, content_desc, content_encoding, None, size)
