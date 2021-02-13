
from __future__ import annotations

from collections.abc import Mapping, Sequence
from email.headerregistry import Address, AddressHeader, SingleAddressHeader, \
    UnstructuredHeader, DateHeader, ContentDispositionHeader, \
    ContentTransferEncodingHeader
from itertools import chain
from typing import Any, SupportsBytes, Optional, Union

from ..primitives import List, Nil, Number, String
from ..specials import DateTime
from ...bytes import Writeable, WriteStream

__all__ = ['EnvelopeStructure', 'BodyStructure', 'MultipartBodyStructure',
           'ContentBodyStructure', 'TextBodyStructure', 'MessageBodyStructure']

_CTEHeader = ContentTransferEncodingHeader


class _Concatenated(Writeable):

    def __init__(self, parts: Sequence[SupportsBytes]) -> None:
        super().__init__()
        self.parts = parts

    def write(self, writer: WriteStream) -> None:
        for part in self.parts:
            writer.write(bytes(part))

    def __bytes__(self) -> bytes:
        return b''.join([bytes(part) for part in self.parts])


class _AddressList(Writeable):

    def __init__(self, headers: Optional[Sequence[AddressHeader]]) -> None:
        super().__init__()
        self.headers: Sequence[AddressHeader] = headers or []

    @classmethod
    def _parse(cls, address: Address):
        realname = String.build(address.display_name)
        localpart = String.build(address.username)
        domain = String.build(address.domain)
        return List([realname, Nil(), localpart, domain])

    @property
    def _value(self) -> Writeable:
        if self.headers:
            addresses: list[Address] = []
            for header in self.headers:
                if isinstance(header, SingleAddressHeader):
                    addresses.append(header.address)
                else:
                    addresses.extend(header.addresses)
            return List([self._parse(address)
                         for address in addresses])
        else:
            return Nil()

    def write(self, writer: WriteStream) -> None:
        self._value.write(writer)

    def __bytes__(self) -> bytes:
        return bytes(self._value)


class _ParamsList(Writeable):

    def __init__(self, params: Optional[Mapping[str, Any]]) -> None:
        super().__init__()
        self.params = params

    @property
    def _value(self) -> Writeable:
        if self.params:
            values = [(String.build(key), String.build(value))
                      for key, value in self.params.items()]
            return List(chain.from_iterable(values))
        else:
            return Nil()

    def write(self, writer: WriteStream) -> None:
        self._value.write(writer)

    def __bytes__(self) -> bytes:
        return bytes(self._value)


class EnvelopeStructure(Writeable):
    """Builds the response to an `RFC 3501 7.4.2
    <https://tools.ietf.org/html/rfc3501#section-7.4.2>`_ FETCH ENVELOPE
    request.

    Args:
        date: Original date of the message.
        subject: ``Subject:`` header.
        from_: ``From:`` headers.
        sender: ``Sender:`` headers.
        reply_to: ``Reply-To:`` headers.
        to: ``To:`` headers.
        cc: ``Cc:`` headers.
        bcc: ``Bcc`` headers.
        in_reply_to: ``In-Reply-To:`` header.
        message_id: ``Message-Id:`` header.

    """

    def __init__(self, date: Optional[DateHeader],
                 subject: Optional[UnstructuredHeader],
                 from_: Optional[Sequence[AddressHeader]],
                 sender: Optional[Sequence[SingleAddressHeader]],
                 reply_to: Optional[Sequence[AddressHeader]],
                 to: Optional[Sequence[AddressHeader]],
                 cc: Optional[Sequence[AddressHeader]],
                 bcc: Optional[Sequence[AddressHeader]],
                 in_reply_to: Optional[UnstructuredHeader],
                 message_id: Optional[UnstructuredHeader]) -> None:
        super().__init__()
        self.date = date
        self.subject = subject
        self.from_ = from_
        self.sender = sender
        self.reply_to = reply_to
        self.to = to
        self.cc = cc
        self.bcc = bcc
        self.in_reply_to = in_reply_to
        self.message_id = message_id

    @classmethod
    def empty(cls) -> EnvelopeStructure:
        """Return an empty envelope structure object.

        See Also:
            `RFC 2180 4.1.3
            <https://tools.ietf.org/html/rfc2180#section-4.1.3>`_

        """
        return _EmptyEnvelopeStructure()

    def _addresses(self, headers: Optional[Sequence[AddressHeader]],
                   fallback: Optional[Sequence[AddressHeader]] = None) \
            -> SupportsBytes:
        if not headers and fallback:
            return self._addresses(fallback)
        return _AddressList(headers)

    @property
    def _value(self) -> Writeable:
        datetime: Union[DateTime, Nil] = \
            DateTime(self.date.datetime) if self.date else Nil()
        return List([datetime,
                     String.build(self.subject),
                     self._addresses(self.from_),
                     self._addresses(self.sender, self.from_),
                     self._addresses(self.reply_to, self.from_),
                     self._addresses(self.to),
                     self._addresses(self.cc),
                     self._addresses(self.bcc),
                     String.build(self.in_reply_to),
                     String.build(self.message_id)])

    def write(self, writer: WriteStream) -> None:
        self._value.write(writer)

    def __bytes__(self) -> bytes:
        return bytes(self._value)


class BodyStructure(Writeable):
    """Parent class for the response to an `RFC 3501 7.4.2
    <https://tools.ietf.org/html/rfc3501#section-7.4.2>`_ FETCH BODYSTRUCTURE
    request. This class should not be used directly.

    Args:
        maintype: Main-type of the ``Content-Type:`` header.
        subtype: Sub-type of the ``Content-Type:`` header.
        content_type_params: Parameters from the ``Content-Type:`` header.
        content_disposition: ``Content-Disposition:`` header.
        content_language: ``Content-Language:`` header.
        content_location: ``Content-Location:`` header.

    """

    def __init__(self, maintype: str, subtype: str,
                 content_type_params: Optional[Mapping[str, Any]],
                 content_disposition: Optional[ContentDispositionHeader],
                 content_language: Optional[UnstructuredHeader],
                 content_location: Optional[UnstructuredHeader]) -> None:
        super().__init__()
        self.maintype = maintype
        self.subtype = subtype
        self.content_type_params = content_type_params
        self.content_disposition = content_disposition
        self.content_language = content_language
        self.content_location = content_location

    @classmethod
    def empty(cls) -> BodyStructure:
        """Return an empty body structure object.

        See Also:
            `RFC 2180 4.1.3
            <https://tools.ietf.org/html/rfc2180#section-4.1.3>`_

        """
        return _EmptyBodyStructure()

    @property
    def _value(self) -> List:
        raise NotImplementedError

    def write(self, writer: WriteStream) -> None:
        self._value.write(writer)

    def __bytes__(self) -> bytes:
        return bytes(self._value)

    @property
    def extended(self) -> List:
        """The body structure attributes with extension data."""
        raise NotImplementedError


class MultipartBodyStructure(BodyStructure):
    """:class:`BodyStructure` sub-class for ``multipart/*`` messages. The
    response is made up of the BODYSTRUCTUREs of all sub-parts.

    Args:
        subtype: Sub-type of the ``Content-Type:`` header.
        content_type_params: Parameters from the ``Content-Type:`` header.
        content_disposition: ``Content-Disposition:`` header.
        content_language: ``Content-Language:`` header.
        content_location: ``Content-Location:`` header.
        parts: Sub-part body structure objects.

    """

    def __init__(self, subtype: str,
                 content_type_params: Optional[Mapping[str, Any]],
                 content_disposition: Optional[ContentDispositionHeader],
                 content_language: Optional[UnstructuredHeader],
                 content_location: Optional[UnstructuredHeader],
                 parts: Sequence[BodyStructure]) -> None:
        super().__init__('multipart', subtype, content_type_params,
                         content_disposition, content_language,
                         content_location)
        self.parts = parts

    @property
    def _value(self) -> List:
        return List([_Concatenated(self.parts), String.build(self.subtype)])

    @property
    def extended(self) -> List:
        """The body structure attributes with extension data."""
        parts = [part.extended for part in self.parts]
        return List([_Concatenated(parts), String.build(self.subtype),
                     _ParamsList(self.content_type_params),
                     String.build(self.content_disposition),
                     String.build(self.content_language),
                     String.build(self.content_location)])


class ContentBodyStructure(BodyStructure):
    """:class:`BodyStructure` sub-class for any content type that does not
    fit the other sub-classes.

    Args:
        maintype: Main-type of the ``Content-Type:`` header.
        subtype: Sub-type of the ``Content-Type:`` header.
        content_type_params: Parameters from the ``Content-Type:`` header.
        content_disposition: ``Content-Disposition:`` header.
        content_language: ``Content-Language:`` header.
        content_location: ``Content-Location:`` header.
        content_id: ``Content-Id:`` header.
        content_description: ``Content-Description:`` header.
        content_transfer_encoding: ``Content-Transfer-Encoding:`` header.
        body_md5: MD5 hash of the body content.
        size: Size of the message body, in bytes.

    """

    def __init__(self, maintype: str, subtype: str,
                 content_type_params: Optional[Mapping[str, Any]],
                 content_disposition: Optional[ContentDispositionHeader],
                 content_language: Optional[UnstructuredHeader],
                 content_location: Optional[UnstructuredHeader],
                 content_id: Optional[UnstructuredHeader],
                 content_description: Optional[UnstructuredHeader],
                 content_transfer_encoding: Optional[_CTEHeader],
                 body_md5: Optional[str],
                 size: int) -> None:
        super().__init__(maintype, subtype, content_type_params,
                         content_disposition, content_language,
                         content_location)
        self.content_id = content_id
        self.content_description = content_description
        self.content_transfer_encoding = content_transfer_encoding
        self.body_md5 = body_md5
        self.size = size

    @property
    def _value(self) -> List:
        return List([String.build(self.maintype), String.build(self.subtype),
                     _ParamsList(self.content_type_params),
                     String.build(self.content_id),
                     String.build(self.content_description),
                     String.build(self.content_transfer_encoding,
                                  fallback=b'7BIT'),
                     Number(self.size)])

    @property
    def extended(self) -> List:
        """The body structure attributes with extension data."""
        return List([String.build(self.maintype), String.build(self.subtype),
                     _ParamsList(self.content_type_params),
                     String.build(self.content_id),
                     String.build(self.content_description),
                     String.build(self.content_transfer_encoding,
                                  fallback=b'7BIT'),
                     Number(self.size),
                     String.build(self.body_md5),
                     String.build(self.content_disposition),
                     String.build(self.content_language),
                     String.build(self.content_location)])


class TextBodyStructure(ContentBodyStructure):
    """:class:`BodyStructure` sub-class for ``text/*`` messages.

    Args:
        subtype: Sub-type of the ``Content-Type:`` header.
        content_type_params: Parameters from the ``Content-Type:`` header.
        content_disposition: ``Content-Disposition:`` header.
        content_language: ``Content-Language:`` header.
        content_location: ``Content-Location:`` header.
        content_id: ``Content-Id:`` header.
        content_description: ``Content-Description:`` header.
        content_transfer_encoding: ``Content-Transfer-Encoding:`` header.
        body_md5: MD5 hash of the body content.
        size: Size of the message body, in bytes.
        lines: Length of the message body, in lines.

    """

    def __init__(self, subtype: str,
                 content_type_params: Optional[Mapping[str, Any]],
                 content_disposition: Optional[ContentDispositionHeader],
                 content_language: Optional[UnstructuredHeader],
                 content_location: Optional[UnstructuredHeader],
                 content_id: Optional[UnstructuredHeader],
                 content_description: Optional[UnstructuredHeader],
                 content_transfer_encoding: Optional[_CTEHeader],
                 body_md5: Optional[str],
                 size: int, lines: int) -> None:
        super().__init__('text', subtype, content_type_params,
                         content_disposition, content_language,
                         content_location, content_id, content_description,
                         content_transfer_encoding, body_md5, size)
        self.lines = lines

    @property
    def _value(self) -> List:
        return List([String.build(self.maintype), String.build(self.subtype),
                     _ParamsList(self.content_type_params),
                     String.build(self.content_id),
                     String.build(self.content_description),
                     String.build(self.content_transfer_encoding,
                                  fallback=b'7BIT'),
                     Number(self.size), Number(self.lines)])

    @property
    def extended(self) -> List:
        """The body structure attributes with extension data."""
        return List([String.build(self.maintype), String.build(self.subtype),
                     _ParamsList(self.content_type_params),
                     String.build(self.content_id),
                     String.build(self.content_description),
                     String.build(self.content_transfer_encoding,
                                  fallback=b'7BIT'),
                     Number(self.size), Number(self.lines),
                     String.build(self.body_md5),
                     String.build(self.content_disposition),
                     String.build(self.content_language),
                     String.build(self.content_location)])


class MessageBodyStructure(ContentBodyStructure):
    """:class:`BodyStructure` sub-class for ``message/rfc822`` messages.

    Args:
        content_type_params: Parameters from the ``Content-Type:`` header.
        content_disposition: ``Content-Disposition:`` header.
        content_language: ``Content-Language:`` header.
        content_location: ``Content-Location:`` header.
        content_id: ``Content-Id:`` header.
        content_description: ``Content-Description:`` header.
        content_transfer_encoding: ``Content-Transfer-Encoding:`` header.
        body_md5: MD5 hash of the body content.
        size: Size of the message body, in bytes.
        lines: Length of the message body, in lines.
        envelope_structure: Contained message's envelope structure.
        body_structure: Contained message's body structure.

    """

    def __init__(self, content_type_params: Optional[Mapping[str, Any]],
                 content_disposition: Optional[ContentDispositionHeader],
                 content_language: Optional[UnstructuredHeader],
                 content_location: Optional[UnstructuredHeader],
                 content_id: Optional[UnstructuredHeader],
                 content_description: Optional[UnstructuredHeader],
                 content_transfer_encoding: Optional[_CTEHeader],
                 body_md5: Optional[str],
                 size: int, lines: int,
                 envelope_structure: EnvelopeStructure,
                 body_structure: BodyStructure) -> None:
        super().__init__('message', 'rfc822', content_type_params,
                         content_disposition, content_language,
                         content_location, content_id, content_description,
                         content_transfer_encoding, body_md5, size)
        self.lines = lines
        self.envelope_structure = envelope_structure
        self.body_structure = body_structure

    @property
    def _value(self) -> List:
        return List([String.build(self.maintype), String.build(self.subtype),
                     _ParamsList(self.content_type_params),
                     String.build(self.content_id),
                     String.build(self.content_description),
                     String.build(self.content_transfer_encoding,
                                  fallback=b'7BIT'),
                     Number(self.size),
                     self.envelope_structure,
                     self.body_structure,
                     Number(self.lines)])

    @property
    def extended(self) -> List:
        """The body structure attributes with extension data."""
        return List([String.build(self.maintype), String.build(self.subtype),
                     _ParamsList(self.content_type_params),
                     String.build(self.content_id),
                     String.build(self.content_description),
                     String.build(self.content_transfer_encoding,
                                  fallback=b'7BIT'),
                     Number(self.size),
                     self.envelope_structure,
                     self.body_structure.extended,
                     Number(self.lines),
                     String.build(self.body_md5),
                     String.build(self.content_disposition),
                     String.build(self.content_language),
                     String.build(self.content_location)])


class _EmptyEnvelopeStructure(EnvelopeStructure):

    def __init__(self) -> None:
        super().__init__(None, None, None, None, None, None, None, None,
                         None, None)


class _EmptyBodyStructure(TextBodyStructure):

    def __init__(self) -> None:
        super().__init__('plain', None, None, None, None, None,
                         None, None, None, 0, 0)
