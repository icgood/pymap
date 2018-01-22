# Copyright (c) 2014 Ian C. Good
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

import email
import io
from datetime import datetime
from email.charset import Charset
from email.generator import BytesGenerator
from email.message import Message
from email.policy import SMTP
from email.utils import getaddresses
from typing import (TYPE_CHECKING, Optional, Union, Tuple, Iterable, Set,
                    AbstractSet, FrozenSet)

from .flag import SessionFlags
from .parsing import Parseable
from .parsing.primitives import Nil, QuotedString, List, LiteralString, Number
from .parsing.specials import Flag

__all__ = ['MessageStructure']

if TYPE_CHECKING:  # avoid import cycles
    from .interfaces import MailboxState


class ConcatenatedParseables(Parseable):

    def __init__(self, parseables):
        super().__init__()
        self.parseables = parseables
        self._raw = None

    def __bytes__(self):
        if self._raw is not None:
            return self._raw
        self._raw = raw = b''.join(
            [bytes(parseable) for parseable in self.parseables])
        return raw


class TextOnlyBytesGenerator(BytesGenerator):
    # This should produce a bytestring of a email.message.Message object
    # without including any headers, by exploting the internal _write_headers
    # method.

    def _write_headers(self, *args, **kwargs):
        pass


class MessageStructure:
    """Pulls the information from a message object
    necessary to gather `message attributes
    <https://tools.ietf.org/html/rfc3501#section-2.3>`_, as needed by the
    `FETCH responses <https://tools.ietf.org/html/rfc3501#section-7.4.2>`_.

    :param uid: The UID of the message.
    :param message: The message object.
    :param permanent_flags: Permanent flags for the message.
    :param session_flags: Sessions flags for the message.
    :param internal_date: The internal date of the message.

    """

    _HEADER_CHARSET = Charset('utf-8')

    def __init__(self, uid: int, message: Message,
                 permanent_flags: Iterable[Flag] = None,
                 session_flags: SessionFlags = None,
                 internal_date: datetime = None):
        super().__init__()

        #: The message's unique identifier in the mailbox.
        self.uid = uid  # type: int

        #: The MIME-parsed message object.
        self.message = message  # type: Message

        #: The message's internal date.
        self.internal_date = internal_date  # type: Optional[datetime]

        #: The message's set of permanent flags.
        self.permanent_flags = set(permanent_flags or [])  # type: Set[Flag]

        #: The message's set of session flags.
        self.session_flags = (
            session_flags or SessionFlags()
        )  # type: SessionFlags

    def get_flags(self, selected: Optional['MailboxState']) -> FrozenSet[Flag]:
        """Get the full set of permanent and session flags.

        :param selected: The selected mailbox object, used to key the
                        session flags.

        """
        if selected:
            session_flags = self.session_flags.get(selected)
        else:
            session_flags = frozenset()
        return frozenset(self.permanent_flags) | session_flags

    def _get_str_or_nil(self, value):
        if value is None:
            return Nil()
        try:
            return QuotedString(bytes(value, 'ascii'))
        except UnicodeEncodeError:
            value_encoded = self._HEADER_CHARSET.header_encode(value)
            return QuotedString(bytes(value_encoded, 'ascii'))

    def _get_header_str_or_nil(self, msg, name):
        value = msg.get(name)
        return self._get_str_or_nil(value)

    def _get_header_addresses_or_nil(self, msg, name, default_name=None):
        values = msg.get_all(name)
        if not values:
            if default_name:
                values = msg.get_all(default_name)
            if not values:
                return Nil()
        ret = []
        for realname, address in getaddresses(values):
            realname = self._get_str_or_nil(realname)
            localpart, _, domain = address.rpartition('@')
            localpart = self._get_str_or_nil(localpart)
            domain = self._get_str_or_nil(domain)
            ret.append(List([realname, Nil(), localpart, domain]))
        return List(ret)

    def _get_header_params(self, msg):
        ret = []
        for key, value in msg.get_params():
            if key.lower() == msg.get_content_type():
                continue
            ret.append(self._get_str_or_nil(key))
            ret.append(self._get_str_or_nil(value))
        return List(ret)

    @classmethod
    def _get_subparts(cls, self):
        assert self.message.is_multipart()
        return [cls(self.uid, subpart)
                for subpart in self.message.get_payload()]

    @classmethod
    def _get_subpart(cls, msg, section):
        if section:
            subpart = msg
            for i in section:
                if msg.is_multipart():
                    subpart = subpart.get_payload(i - 1)
                elif i == 1:
                    pass
                else:
                    raise IndexError(i)
            return subpart
        else:
            return msg

    def get_headers(self, section: Optional[Iterable[int]] = None,
                    subset: AbstractSet[bytes] = None,
                    inverse: bool = False) \
            -> Union[LiteralString, Nil]:
        """Get the headers from the message.

        The ``section`` argument can index a nested sub-part of the message.
        For example, ``[2, 3]`` would get the 2nd sub-part of the message and
        then index it for its 3rd sub-part.

        :param section: Optional nested list of sub-part indexes.
        :param subset: Subset of headers to get.
        :param inverse: If ``subset`` is given, this flag will invert it
                             so that the headers *not* in ``subset`` are
                             returned.

        """
        try:
            msg = self._get_subpart(self.message, section)
        except IndexError:
            return Nil()
        ret = email.message.Message(SMTP)
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
        return LiteralString(bytes(ret))

    def get_body(self, section: Optional[Iterable[int]] = None) \
            -> Union[LiteralString, Nil]:
        """Get the full body of the message part, including headers.

        The ``section`` argument can index a nested sub-part of the message.
        For example, ``[2, 3]`` would get the 2nd sub-part of the message and
        then index it for its 3rd sub-part.

        :param section: Optional nested list of sub-part indexes.

        """
        try:
            msg = self._get_subpart(self.message, section)
        except IndexError:
            return Nil()
        return LiteralString(bytes(msg))

    def get_text(self, section: Optional[Iterable[int]] = None) \
            -> Union[LiteralString, Nil]:
        """Get the text of the message part, not including headers.

        The ``section`` argument can index a nested sub-part of the message.
        For example, ``[2, 3]`` would get the 2nd sub-part of the message and
        then index it for its 3rd sub-part.

        :param section: Optional nested list of sub-part indexes.

        """
        try:
            msg = self._get_subpart(self.message, section)
        except IndexError:
            return Nil()
        ofp = io.BytesIO()
        TextOnlyBytesGenerator(ofp, False, policy=SMTP).flatten(msg)
        return LiteralString(ofp.getvalue())

    @classmethod
    def _get_size(cls, msg: Message) -> Number:
        data = bytes(msg)
        size = len(data)
        return Number(size)

    @classmethod
    def _get_size_with_lines(cls, msg: Message) -> Tuple[Number, Number]:
        data = bytes(msg)
        size = len(data)
        lines = data.count(b'\n')
        return Number(size), Number(lines)

    def get_size(self) -> Number:
        """Return the size of the message, in octets."""
        return self._get_size(self.message)

    async def get_envelope_structure(self) -> List:
        """Build and return the envelope structure.

        .. seealso::

           `RFC 3501 2.3.5
           <https://tools.ietf.org/html/rfc3501#section-2.3.5>`_

        """
        msg = self.message
        return List([self._get_header_str_or_nil(msg, 'Date'),
                     self._get_header_str_or_nil(msg, 'Subject'),
                     self._get_header_addresses_or_nil(msg, 'From'),
                     self._get_header_addresses_or_nil(msg, 'Sender', 'From'),
                     self._get_header_addresses_or_nil(
                         msg, 'Reply-To', 'From'),
                     self._get_header_addresses_or_nil(msg, 'To'),
                     self._get_header_addresses_or_nil(msg, 'Cc'),
                     self._get_header_addresses_or_nil(msg, 'Bcc'),
                     self._get_header_str_or_nil(msg, 'In-Reply-To'),
                     self._get_header_str_or_nil(msg, 'Message-Id')])

    def get_body_structure(self) -> List:
        """Build and return the body structure.

        .. seealso::

           `RFC 3501 2.3.6
           <https://tools.ietf.org/html/rfc3501#section-2.3.6>`_

        """
        msg = self.message
        maintype = self._get_str_or_nil(msg.get_content_maintype())
        subtype = self._get_str_or_nil(msg.get_content_subtype())
        if maintype.value == b'multipart':
            child_data = []
            for struct in self._get_subparts(self):
                child_data.append(struct.get_body_structure())
            return List([ConcatenatedParseables(child_data), subtype])
        params = self._get_header_params(msg)
        cid = self._get_header_str_or_nil(msg, 'Content-Id')
        desc = self._get_header_str_or_nil(msg, 'Content-Description')
        encoding = self._get_header_str_or_nil(
            msg, 'Content-Transfer-Encoding')
        if maintype.value == b'message' and subtype.value == b'rfc822':
            size, lines = self._get_size_with_lines(msg)
            child_structs = self._get_subparts(self)
            sub_message = child_structs[0]
            sub_message_env = sub_message.get_envelope_structure()
            sub_message_body = sub_message.get_body_structure()
            return List([maintype, subtype, params, cid, desc, encoding, size,
                         sub_message_env, sub_message_body, lines])
        elif maintype.value == b'text':
            size, lines = self._get_size_with_lines(msg)
            return List(
                [maintype, subtype, params, cid, desc, encoding, size, lines])
        size = self._get_size(msg)
        return List([maintype, subtype, params, cid, desc, encoding, size])
