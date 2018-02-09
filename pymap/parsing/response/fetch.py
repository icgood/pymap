# Copyright (c) 2018 Ian C. Good
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#

from email.headerregistry import Address, AddressHeader, UnstructuredHeader, \
    DateHeader, ContentDispositionHeader
from itertools import chain
from typing import SupportsBytes, Optional, Dict, List as ListT

from ..specials import DateTime
from ..primitives import List, Nil, Number, String

__all__ = ['EnvelopeStructure', 'BodyStructure', 'MultipartBodyStructure',
           'ContentBodyStructure', 'TextBodyStructure', 'MessageBodyStructure']


class _Concatenated:

    def __init__(self, parts: ListT[SupportsBytes]):
        self.parts = parts

    def __bytes__(self):
        return b''.join([bytes(part) for part in self.parts])


class _AddressList:

    def __init__(self, headers: Optional[ListT[AddressHeader]]):
        super().__init__()
        self.headers = headers or []  # type: ListT[AddressHeader]

    @classmethod
    def _parse(cls, address: Address):
        realname = String.build(address.display_name)
        localpart = String.build(address.username)
        domain = String.build(address.domain)
        return List([realname, Nil(), localpart, domain])

    @property
    def _value(self) -> SupportsBytes:
        if self.headers:
            return List([self._parse(address)
                         for header in self.headers
                         for address in header.addresses])
        else:
            return Nil()

    def __bytes__(self):
        return bytes(self._value)


class _ParamsList:

    def __init__(self, params: Dict[str, str]):
        super().__init__()
        self.params = params

    @property
    def _value(self) -> SupportsBytes:
        if self.params:
            values = [(String.build(key), String.build(value))
                      for key, value in self.params.items()]
            return List(chain.from_iterable(values))
        else:
            return Nil()

    def __bytes__(self):
        return bytes(self._value)


class EnvelopeStructure:
    """Builds the response to an `RFC 3501 7.4.2
    <https://tools.ietf.org/html/rfc3501#section-7.4.2>`_ FETCH ENVELOPE
    request.

    :param date: Original date of the message.
    :param subject: ``Subject:`` header.
    :param from_: ``From:`` headers.
    :param sender: ``Sender:`` headers.
    :param reply_to: ``Reply-To:`` headers.
    :param to: ``To:`` headers.
    :param cc: ``Cc:`` headers.
    :param bcc: ``Bcc`` headers.
    :param in_reply_to: ``In-Reply-To:`` header.
    :param message_id: ``Message-Id:`` header.

    """

    def __init__(self, date: Optional[DateHeader],
                 subject: Optional[UnstructuredHeader],
                 from_: Optional[ListT[AddressHeader]],
                 sender: Optional[ListT[AddressHeader]],
                 reply_to: Optional[ListT[AddressHeader]],
                 to: Optional[ListT[AddressHeader]],
                 cc: Optional[ListT[AddressHeader]],
                 bcc: Optional[ListT[AddressHeader]],
                 in_reply_to: Optional[UnstructuredHeader],
                 message_id: Optional[UnstructuredHeader]):
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

    def _addresses(self, headers: Optional[ListT[AddressHeader]],
                   fallback: Optional[ListT[AddressHeader]] = None) \
            -> SupportsBytes:
        if not headers and fallback:
            return self._addresses(fallback)
        return _AddressList(headers)

    @property
    def _value(self) -> SupportsBytes:
        return List([DateTime(self.date.datetime) if self.date else Nil(),
                     String.build(self.subject),
                     self._addresses(self.from_),
                     self._addresses(self.sender, self.from_),
                     self._addresses(self.reply_to, self.from_),
                     self._addresses(self.to),
                     self._addresses(self.cc),
                     self._addresses(self.bcc),
                     String.build(self.in_reply_to),
                     String.build(self.message_id)])

    def __bytes__(self):
        return bytes(self._value)


class BodyStructure:
    """Parent class for the response to an `RFC 3501 7.4.2
    <https://tools.ietf.org/html/rfc3501#section-7.4.2>`_ FETCH BODYSTRUCTURE
    request. This class should not be used directly.

    :param maintype: Main-type of the ``Content-Type:`` header.
    :param subtype: Sub-type of the ``Content-Type:`` header.
    :param content_type_params: Parameters from the ``Content-Type:`` header.
    :param content_disposition: ``Content-Disposition:`` header.
    :param content_language: ``Content-Language:`` header.
    :param content_location: ``Content-Location:`` header.

    """

    def __init__(self, maintype: str, subtype: str,
                 content_type_params: Optional[Dict[str, str]],
                 content_disposition: Optional[ContentDispositionHeader],
                 content_language: Optional[UnstructuredHeader],
                 content_location: Optional[UnstructuredHeader]):
        super().__init__()
        self.maintype = maintype
        self.subtype = subtype
        self.content_type_params = content_type_params
        self.content_disposition = content_disposition
        self.content_language = content_language
        self.content_location = content_location

    @property
    def _value(self) -> List:
        raise NotImplementedError

    def __bytes__(self):
        return bytes(self._value)

    @property
    def extended(self) -> List:
        """The body structure attributes with extension data."""
        raise NotImplementedError


class MultipartBodyStructure(BodyStructure):
    """:class:`BodyStructure` sub-class for ``multipart/*`` messages. The
    response is made up of the BODYSTRUCTUREs of all sub-parts.

    :param subtype: Sub-type of the ``Content-Type:`` header.
    :param content_type_params: Parameters from the ``Content-Type:`` header.
    :param content_disposition: ``Content-Disposition:`` header.
    :param content_language: ``Content-Language:`` header.
    :param content_location: ``Content-Location:`` header.
    :param parts: Sub-part body structure objects.

    """

    def __init__(self, subtype: str,
                 content_type_params: Optional[Dict[str, str]],
                 content_disposition: Optional[ContentDispositionHeader],
                 content_language: Optional[UnstructuredHeader],
                 content_location: Optional[UnstructuredHeader],
                 parts: ListT[BodyStructure]):
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

    :param maintype: Main-type of the ``Content-Type:`` header.
    :param subtype: Sub-type of the ``Content-Type:`` header.
    :param content_type_params: Parameters from the ``Content-Type:`` header.
    :param content_disposition: ``Content-Disposition:`` header.
    :param content_language: ``Content-Language:`` header.
    :param content_location: ``Content-Location:`` header.
    :param content_id: ``Content-Id:`` header.
    :param content_description: ``Content-Description:`` header.
    :param content_transfer_encoding: ``Content-Transfer-Encoding:`` header.
    :param body_md5: MD5 hash of the body content.
    :param size: Size of the message body, in bytes.

    """

    def __init__(self, maintype: str, subtype: str,
                 content_type_params: Optional[Dict[str, str]],
                 content_disposition: Optional[ContentDispositionHeader],
                 content_language: Optional[UnstructuredHeader],
                 content_location: Optional[UnstructuredHeader],
                 content_id: Optional[UnstructuredHeader],
                 content_description: Optional[UnstructuredHeader],
                 content_transfer_encoding: Optional[UnstructuredHeader],
                 body_md5: Optional[str],
                 size: int):
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
                     String.build(self.content_transfer_encoding),
                     Number(self.size)])

    @property
    def extended(self) -> List:
        """The body structure attributes with extension data."""
        return List([String.build(self.maintype), String.build(self.subtype),
                     _ParamsList(self.content_type_params),
                     String.build(self.content_id),
                     String.build(self.content_description),
                     String.build(self.content_transfer_encoding),
                     Number(self.size),
                     String.build(self.body_md5),
                     String.build(self.content_disposition),
                     String.build(self.content_language),
                     String.build(self.content_location)])


class TextBodyStructure(ContentBodyStructure):
    """:class:`BodyStructure` sub-class for ``text/*`` messages.

    :param subtype: Sub-type of the ``Content-Type:`` header.
    :param content_type_params: Parameters from the ``Content-Type:`` header.
    :param content_disposition: ``Content-Disposition:`` header.
    :param content_language: ``Content-Language:`` header.
    :param content_location: ``Content-Location:`` header.
    :param content_id: ``Content-Id:`` header.
    :param content_description: ``Content-Description:`` header.
    :param content_transfer_encoding: ``Content-Transfer-Encoding:`` header.
    :param body_md5: MD5 hash of the body content.
    :param size: Size of the message body, in bytes.
    :param lines: Length of the message body, in lines.

    """

    def __init__(self, subtype: str,
                 content_type_params: Optional[Dict[str, str]],
                 content_disposition: Optional[ContentDispositionHeader],
                 content_language: Optional[UnstructuredHeader],
                 content_location: Optional[UnstructuredHeader],
                 content_id: Optional[UnstructuredHeader],
                 content_description: Optional[UnstructuredHeader],
                 content_transfer_encoding: Optional[UnstructuredHeader],
                 body_md5: Optional[str],
                 size: int, lines: int):
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
                     String.build(self.content_transfer_encoding),
                     Number(self.size), Number(self.lines)])

    @property
    def extended(self) -> List:
        """The body structure attributes with extension data."""
        return List([String.build(self.maintype), String.build(self.subtype),
                     _ParamsList(self.content_type_params),
                     String.build(self.content_id),
                     String.build(self.content_description),
                     String.build(self.content_transfer_encoding),
                     Number(self.size), Number(self.lines),
                     String.build(self.body_md5),
                     String.build(self.content_disposition),
                     String.build(self.content_language),
                     String.build(self.content_location)])


class MessageBodyStructure(ContentBodyStructure):
    """:class:`BodyStructure` sub-class for ``message/rfc822`` messages.

    :param content_type_params: Parameters from the ``Content-Type:`` header.
    :param content_disposition: ``Content-Disposition:`` header.
    :param content_language: ``Content-Language:`` header.
    :param content_location: ``Content-Location:`` header.
    :param content_id: ``Content-Id:`` header.
    :param content_description: ``Content-Description:`` header.
    :param content_transfer_encoding: ``Content-Transfer-Encoding:`` header.
    :param body_md5: MD5 hash of the body content.
    :param size: Size of the message body, in bytes.
    :param lines: Length of the message body, in lines.
    :param envelope_structure: Contained message's envelope structure.
    :param body_structure: Contained message's body structure.

    """

    def __init__(self, content_type_params: Optional[Dict[str, str]],
                 content_disposition: Optional[ContentDispositionHeader],
                 content_language: Optional[UnstructuredHeader],
                 content_location: Optional[UnstructuredHeader],
                 content_id: Optional[str],
                 content_description: Optional[str],
                 content_transfer_encoding: Optional[str],
                 body_md5: Optional[str],
                 size: int, lines: int,
                 envelope_structure: EnvelopeStructure,
                 body_structure: BodyStructure):
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
                     String.build(self.content_transfer_encoding),
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
                     String.build(self.content_transfer_encoding),
                     Number(self.size),
                     self.envelope_structure,
                     self.body_structure.extended,
                     Number(self.lines),
                     String.build(self.body_md5),
                     String.build(self.content_disposition),
                     String.build(self.content_language),
                     String.build(self.content_location)])
