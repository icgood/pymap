
from __future__ import annotations

import base64
import quopri
from abc import abstractmethod, ABCMeta
from email.headerregistry import ContentTransferEncodingHeader
from typing import Optional

from . import MessageHeader, MessageBody
from ..bytes import Writeable

__all__ = ['MessageDecoder']


class MessageDecoder(metaclass=ABCMeta):
    """Decodes a :class:`~pymap.mime.MessageBody` as decided by its
    ``Content-Transfer-Encoding`` header.

    Attributes:
        registry (Dict[str, :class:`MessageDecoder`]): Registry of custom
            decoders. Keys should be lower-case.

    """

    registry: dict[str, MessageDecoder] = {}

    @classmethod
    def of(cls, msg_header: MessageHeader) -> MessageDecoder:
        """Return a decoder from the message header object.

        See Also:
            :meth:`.of_cte`

        Args:
            msg_header: The message header object.

        """
        cte_hdr = msg_header.parsed.content_transfer_encoding
        return cls.of_cte(cte_hdr)

    @classmethod
    def of_cte(cls, header: Optional[ContentTransferEncodingHeader]) \
            -> MessageDecoder:
        """Return a decoder from the CTE header value.

        There is built-in support for ``7bit``, ``8bit``, ``quoted-printable``,
        and ``base64`` CTE header values. Decoders can be added or overridden
        with the :attr:`.registry` dictionary.

        Args:
            header: The CTE header value.

        """
        if header is None:
            return _NoopDecoder()
        hdr_str = str(header).lower()
        custom = cls.registry.get(hdr_str)
        if custom is not None:
            return custom
        elif hdr_str in ('7bit', '8bit'):
            return _NoopDecoder()
        elif hdr_str == 'quoted-printable':
            return _QuotedPrintableDecoder()
        elif hdr_str == 'base64':
            return _Base64Decoder()
        else:
            raise NotImplementedError(hdr_str)

    @abstractmethod
    def decode(self, body: MessageBody) -> Writeable:
        """Decode and return the decoded body of the message.

        Args:
            body: The message body.

        """
        ...


class _NoopDecoder(MessageDecoder):

    def decode(self, body: MessageBody) -> Writeable:
        return body


class _QuotedPrintableDecoder(MessageDecoder):

    def decode(self, body: MessageBody) -> Writeable:
        raw = bytes(body)
        ret = quopri.decodestring(raw)
        return Writeable.wrap(ret)


class _Base64Decoder(MessageDecoder):

    def decode(self, body: MessageBody) -> Writeable:
        raw = bytes(body)
        ret = base64.b64decode(raw)
        return Writeable.wrap(ret)
