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

from email.utils import getaddresses
from itertools import chain
from typing import Tuple, List as ListT, SupportsBytes, Optional, Dict

from ..primitives import List, Nil, Number, String

__all__ = ['EnvelopeStructure', 'BodyStructure', 'MultipartBodyStructure',
           'ContentBodyStructure', 'TextBodyStructure', 'MessageBodyStructure']


class _Concatenated:

    def __init__(self, parts: ListT[SupportsBytes]):
        self.parts = parts

    def __bytes__(self):
        return b''.join([bytes(part) for part in self.parts])


class _AddressList:

    def __init__(self, addresses: ListT[str]):
        super().__init__()
        self.addresses = addresses  # type: ListT[str]

    @classmethod
    def _parse(cls, realname, address):
        realname = String.build(realname)
        localpart, _, domain = address.rpartition('@')
        localpart = String.build(localpart)
        domain = String.build(domain)
        return List([realname, Nil(), localpart, domain])

    @property
    def _value(self) -> SupportsBytes:
        if self.addresses:
            addresses = getaddresses(self.addresses)
            return List([self._parse(realname, address)
                         for realname, address in addresses])
        else:
            return Nil()

    def __bytes__(self):
        return bytes(self._value)


class _ParamsList:

    def __init__(self, params: Dict[str, str]):
        super().__init__()
        self.params = params  # type: Dict[str, str]

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

    :param date: The required ``Date:`` header.
    :param subject: The ``Subject:`` header.
    :param from_: The ``From:`` headers.
    :param sender: The ``Sender:`` headers.
    :param reply_to: The ``Reply-To:`` headers.
    :param to: The ``To:`` headers.
    :param cc: The ``Cc:`` headers.
    :param bcc: The ``Bcc`` headers.
    :param in_reply_to: The ``In-Reply-To:`` header.
    :param message_id: The ``Message-Id:`` header.

    """

    def __init__(self, date: str,
                 subject: Optional[str],
                 from_: Optional[ListT[str]],
                 sender: Optional[ListT[str]],
                 reply_to: Optional[ListT[str]],
                 to: Optional[ListT[str]],
                 cc: Optional[ListT[str]],
                 bcc: Optional[ListT[str]],
                 in_reply_to: Optional[str],
                 message_id: Optional[str]):
        super().__init__()
        self.date = date  # type: str
        self.subject = subject  # type: Optional[str]
        self.from_ = from_  # type: Optional[ListT[str]]
        self.sender = sender  # type: Optional[ListT[str]]
        self.reply_to = reply_to  # type: Optional[ListT[str]]
        self.to = to  # type: Optional[ListT[str]]
        self.cc = cc  # type: Optional[ListT[str]]
        self.bcc = bcc  # type: Optional[ListT[str]]
        self.in_reply_to = in_reply_to  # type: Optional[str]
        self.message_id = message_id  # type: Optional[str]

    def _addresses(self, addresses: ListT[str], fallback=None) \
            -> SupportsBytes:
        if not addresses and fallback:
            return self._addresses(fallback)
        return _AddressList(addresses)

    @property
    def _value(self) -> SupportsBytes:
        return List([String.build(self.date),
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

    :param maintype: The main-type of the ``Content-Type:`` header.
    :param subtype: The sub-type of the ``Content-Type:`` header.

    """

    def __init__(self, maintype: str, subtype: str):
        super().__init__()
        self.maintype = maintype  # type: str
        self.subtype = subtype  # type: str

    @property
    def _value(self) -> SupportsBytes:
        raise NotImplementedError

    def __bytes__(self):
        return bytes(self._value)


class MultipartBodyStructure(BodyStructure):
    """:class:`BodyStructure` sub-class for ``multipart/*`` messages. The
    response is made up of the BODYSTRUCTUREs of all sub-parts.

    :param subtype: The sub-type of the ``Content-Type:`` header.
    :param parts: The sub-part body structure objects.

    """

    def __init__(self, subtype: str, parts: ListT[BodyStructure] = None):
        super().__init__('multipart', subtype)
        self.parts = parts or []  # type: ListT[BodyStructure]

    def add(self, part: BodyStructure) -> None:
        """Add a new sub-part to the multipart body structure.

        :param part: The sub-part body structure object.

        """
        self.parts.append(part)

    @property
    def _value(self) -> SupportsBytes:
        return List([_Concatenated(self.parts), String.build(self.subtype)])


class ContentBodyStructure(BodyStructure):
    """:class:`BodyStructure` sub-class for any content type that does not
    fit the other sub-classes.

    :param maintype: The main-type of the ``Content-Type:`` header.
    :param subtype: The sub-type of the ``Content-Type:`` header.
    :param params: The ``Content-Type:`` header parameters.
    :param content_id: The ``Content-Id:`` header.
    :param content_desc: The ``Content-Description:`` header.
    :param content_encoding: The ``Content-Transfer-Encoding:`` header.
    :param size: The size of the message body, in bytes.

    """

    def __init__(self, maintype: str, subtype: str,
                 params: ListT[Tuple[str, str]],
                 content_id: Optional[str],
                 content_desc: Optional[str],
                 content_encoding: Optional[str],
                 size: int):
        super().__init__(maintype, subtype)
        self.params = params  # type: ListT[Tuple[str, str]]
        self.content_id = content_id  # type: Optional[str]
        self.content_desc = content_desc  # type: Optional[str]
        self.content_encoding = content_encoding  # type: Optional[str]
        self.size = size  # type: int

    @property
    def _value(self) -> SupportsBytes:
        return List([String.build(self.maintype), String.build(self.subtype),
                     _ParamsList(self.params),
                     String.build(self.content_id),
                     String.build(self.content_desc),
                     String.build(self.content_encoding),
                     Number(self.size)])


class TextBodyStructure(ContentBodyStructure):
    """:class:`BodyStructure` sub-class for ``text/*`` messages.

    :param subtype: The sub-type of the ``Content-Type:`` header.
    :param params: The ``Content-Type:`` header parameters.
    :param content_id: The ``Content-Id:`` header.
    :param content_desc: The ``Content-Description:`` header.
    :param content_encoding: The ``Content-Transfer-Encoding:`` header.
    :param size: The size of the message body, in bytes.
    :param lines: The lenth of the message body, in lines.

    """

    def __init__(self, subtype: str,
                 params: ListT[Tuple[str, str]],
                 content_id: Optional[str],
                 content_desc: Optional[str],
                 content_encoding: Optional[str],
                 size: int, lines: int):
        super().__init__('text', subtype, params, content_id,
                         content_desc, content_encoding, size)
        self.lines = lines  # type: int

    @property
    def _value(self) -> SupportsBytes:
        return List([String.build(self.maintype), String.build(self.subtype),
                     _ParamsList(self.params),
                     String.build(self.content_id),
                     String.build(self.content_desc),
                     String.build(self.content_encoding),
                     Number(self.size), Number(self.lines)])


class MessageBodyStructure(ContentBodyStructure):
    """:class:`BodyStructure` sub-class for ``message/rfc822`` messages.

    :param params: The ``Content-Type:`` header parameters.
    :param content_id: The ``Content-Id:`` header.
    :param content_desc: The ``Content-Description:`` header.
    :param content_encoding: The ``Content-Transfer-Encoding:`` header.
    :param size: The size of the message body, in bytes.
    :param lines: The lenth of the message body, in lines.
    :param envelope_structure: The contained message's envelope structure.
    :param body_structure: The contained message's body structure.

    """

    def __init__(self, params: ListT[Tuple[str, str]],
                 content_id: Optional[str],
                 content_desc: Optional[str],
                 content_encoding: Optional[str],
                 size: int, lines: int,
                 envelope_structure: EnvelopeStructure,
                 body_structure: BodyStructure):
        super().__init__('message', 'rfc822', params, content_id,
                         content_desc, content_encoding, size)
        self.lines = lines  # type: int
        self.envelope_structure = envelope_structure  # type: EnvelopeStructure
        self.body_structure = body_structure  # type: BodyStructure

    @property
    def _value(self) -> SupportsBytes:
        return List([String.build(self.maintype), String.build(self.subtype),
                     _ParamsList(self.params),
                     String.build(self.content_id),
                     String.build(self.content_desc),
                     String.build(self.content_encoding),
                     Number(self.size),
                     self.envelope_structure,
                     self.body_structure,
                     Number(self.lines)])
