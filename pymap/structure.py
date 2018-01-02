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
from email.charset import Charset
from email.generator import BytesGenerator
from email.message import Message
from email.policy import SMTP
from email.utils import getaddresses

from .parsing import Parseable
from .parsing.primitives import Nil, QuotedString, List, LiteralString, Number

__all__ = ['MessageStructure']


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


class MessageStructure(object):
    """Pulls the information from a message object
    necessary to gather `message attributes
    <https://tools.ietf.org/html/rfc3501#section-2.3>`_, as needed by the
    `FETCH responses <https://tools.ietf.org/html/rfc3501#section-7.4.2>`_.

    :param message: The message object.
    :type message: :class:`~email.message.Message` or
                   :class:`~pymap.interfaces.MessageInterface`

    """

    _HEADER_CHARSET = Charset('utf-8')

    def __init__(self, message):
        super().__init__()
        self.message = message

    async def _get_msg(self, full=False):
        if isinstance(self.message, Message):
            return self.message
        return await self.message.get_message(full=full)

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

    def _get_subparts(self, msg):
        assert msg.is_multipart()
        return [MessageStructure(subpart) for subpart in msg.get_payload()]

    def _get_subpart(self, msg, section):
        subpart = msg
        for i in section:
            if msg.is_multipart():
                subpart = subpart.get_payload(i - 1)
            elif i == 1:
                pass
            else:
                raise IndexError(section)
        return subpart

    async def get_headers(self, section=None, subset=None, inverse=False):
        """Get the headers from the message.

        The ``section`` argument can index a nested sub-part of the message.
        For example, ``[2, 3]`` would get the 2nd sub-part of the message and
        then index it for its 3rd sub-part.

        :param list section: Optional nested list of sub-part indexes.
        :param list subset: Optional subset of headers to get. Each item should
                            be an upper-cased string.
        :param bool inverse: If ``subset`` is given, this flag will invert it
                             so that the headers *not* in ``subset`` are
                             returned.
        :rtype: :class:`pymap.parsing.primitives.LiteralString`

        """
        msg = await self._get_msg(False)
        if section:
            try:
                msg = self._get_subpart(msg, section)
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

    async def get_body(self, section=None):
        """Get the full body of the message part, including headers.

        The ``section`` argument can index a nested sub-part of the message.
        For example, ``[2, 3]`` would get the 2nd sub-part of the message and
        then index it for its 3rd sub-part.

        :param list section: Optional nested list of sub-part indexes.
        :rtype: :class:`pymap.parsing.primitives.LiteralString`

        """
        msg = await self._get_msg()
        if section:
            try:
                msg = self._get_subpart(msg, section)
            except IndexError:
                return Nil()
        return LiteralString(bytes(msg))

    async def get_text(self, section=None):
        """Get the text of the message part, not including headers.

        The ``section`` argument can index a nested sub-part of the message.
        For example, ``[2, 3]`` would get the 2nd sub-part of the message and
        then index it for its 3rd sub-part.

        :param list section: Optional nested list of sub-part indexes.
        :rtype: :class:`pymap.parsing.primitives.LiteralString`

        """
        msg = await self._get_msg()
        if section:
            try:
                msg = self._get_subpart(msg, section)
            except IndexError:
                return Nil()
        ofp = io.BytesIO()
        TextOnlyBytesGenerator(ofp, False, policy=SMTP).flatten(msg)
        return LiteralString(ofp.getvalue())

    async def get_size(self, with_lines=False, msg=None):
        """Return the size of the message, in octets.

        :param with_lines: Return a two-tuple of
                           :class:`~pymap.parsing.primitives.Number` objects
                           with the message size and number of lines.
        :param msg: Use the given object instead of querying :attr:`.message`.
        :type msg: :class:`~email.message.Message`
        :type: :class:`pymap.parsing.primitives.Number`

        """
        msg = msg or (await self._get_msg())
        data = bytes(msg)
        size = len(data)
        if with_lines:
            lines = data.count(b'\n')
            return Number(size), Number(lines)
        else:
            return Number(size)

    async def build_envelope_structure(self, msg=None):
        """Build and return the envelope structure.

        .. seealso::

           `RFC 3501 2.3.5
           <https://tools.ietf.org/html/rfc3501#section-2.3.5>`_

        :param msg: Use the given object instead of querying :attr:`.message`.
        :type msg: :class:`~email.message.Message`
        :rtype: :class:`pymap.parsing.primitives.List`

        """
        msg = msg or (await self._get_msg(False))
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

    async def build_body_structure(self, msg=None, ext_data=False):
        """Build and return the body structure.

        .. seealso::

           `RFC 3501 2.3.6
           <https://tools.ietf.org/html/rfc3501#section-2.3.6>`_

        :param msg: Use the given object instead of querying :attr:`.message`.
        :type msg: :class:`~email.message.Messaege`
        :param bool ext_data: Whether to include extension data in the result.
        :rtype: :class:`pymap.parsing.primitives.List`

        """
        msg = msg or (await self._get_msg())
        maintype = self._get_str_or_nil(msg.get_content_maintype())
        subtype = self._get_str_or_nil(msg.get_content_subtype())
        if maintype.value == b'multipart':
            child_data = []
            for struct in self._get_subparts(msg):
                child_data.append(await struct.build_body_structure())
            return List([ConcatenatedParseables(child_data), subtype])
        params = self._get_header_params(msg)
        id = self._get_header_str_or_nil(msg, 'Content-Id')
        desc = self._get_header_str_or_nil(msg, 'Content-Description')
        encoding = self._get_header_str_or_nil(
            msg, 'Content-Transfer-Encoding')
        if maintype.value == b'message' and subtype.value == b'rfc822':
            size, lines = await self.get_size(True, msg)
            child_structs = self._get_subparts(msg)
            sub_message = child_structs[0]
            sub_message_env = await sub_message.get_envelope_structure()
            sub_message_body = await sub_message.get_body_structure()
            return List([maintype, subtype, params, id, desc, encoding, size,
                         sub_message_env, sub_message_body, lines])
        elif maintype.value == b'text':
            size, lines = await self.get_size(True, msg)
            return List(
                [maintype, subtype, params, id, desc, encoding, size, lines])
        size = await self.get_size(msg=msg)
        return List([maintype, subtype, params, id, desc, encoding, size])
