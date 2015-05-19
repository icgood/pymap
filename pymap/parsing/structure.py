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

import asyncio
from itertools import chain

from email.charset import Charset
from email.utils import getaddresses

from . import Parseable
from .primitives import *  # NOQA

__all__ = ['MessageStructure']


class ConcatenatedParseables(Parseable):

    def __init__(self, parseables):
        super().__init__()
        self.parseables
        self._raw = None

    def __bytes__(self):
        if self._raw is not None:
            return self._raw
        self._raw = raw = b''.join([bytes(parseable)
                                    for parseable in self.parseables])
        return raw


class MessageStructure(object):
    """Given a :class:`email.message.Message`-like object, pull the information
    necessary to construct the envelope and body structures, as described in
    `RFC 3501 2.3.5. <https://tools.ietf.org/html/rfc3501#section-2.3.5>`_ and
    `RFC 3501 2.3.6. <https://tools.ietf.org/html/rfc3501#section-2.3.6>`_.

    :param message: The message object to generate structure for.
    :type message: :class:`~email.message.Message`

    """

    _HEADER_CHARSET = Charset('utf-8')

    def __init__(self, message):
        super().__init__()
        self.message = message

    def _get_str_or_nil(self, value):
        if not value:
            return Nil()
        try:
            return QuotedString(bytes(value, 'ascii'))
        except UnicodeEncodeError:
            value_encoded = cls._HEADER_CHARSET.header_encode(value)
            return QuotedString(bytes(value_encoded, 'ascii'))

    def _get_header_str_or_nil(self, name):
        value = self.message.get(name)
        return self._get_str_or_nil(value)

    def _get_header_addresses_or_nil(self, name, default_name=None):
        values = self.message.get_all(name)
        if not values:
            if default_name:
                values = self.message.get_all(default_name)
            if not values:
                return Nil()
        ret = []
        for realname, address in getaddresses(values):
            realname = cls._get_header_str_or_nil(realname)
            localpart, _, domain = address.rpartition('@')
            localpart = cls._get_header_str_or_nil(localpart)
            domain = cls._get_header_str_or_nil(domain)
            ret.append(List([realname, Nil(), localpart, domain]))
        return List(ret)

    def _get_header_params(self):
        params = self.message.get_params()
        return List([self._get_str_or_nil(item)
                     for item in chain.from_iterable(params)])

    @asyncio.coroutine
    def get_subparts(self):
        """Override this method to change the way sub-parts are fetched from a
        message part. Raises :exc:`AssertionError` if this message part does
        not have sub-parts.

        :raises: AssertionError
        :returns: List of :class:`BodyStructure` objects.

        """
        assert self.message.is_multipart()
        return [MessageStructure(subpart)
                for subpart in self.message.get_payload()]

    @asyncio.coroutine
    def get_size(self, with_lines=False):
        """Override this method to change the way the size and line-length of
        this message part are calculated.

        If ``with_lines`` is True, the return value will be a two-tuple of the
        byte size and the number of lines.

        :param bool with_lines: Whether line count should be included.
        :returns: The size of the message part, in octets.
        :rtype: :class:`~pymap.parsing.primitives.Number`

        """
        data = bytes(self.message)
        size = len(data)
        if with_lines:
            lines = data.count(b'\n')
            return Number(size), Number(lines)
        else:
            return Number(size)

    @asyncio.coroutine
    def build_envelope_structure(self):
        """Build and return the envelope structure.

        :rtype: :class:`pymap.parsing.primitives.List`

        """
        return List([self._get_header_str_or_nil('Date'),
                     self._get_header_str_or_nil('Subject'),
                     self._get_header_addresses_or_nil('From'),
                     self._get_header_addresses_or_nil('Sender', 'From'),
                     self._get_header_addresses_or_nil('Reply-To', 'From'),
                     self._get_header_addresses_or_nil('To'),
                     self._get_header_addresses_or_nil('Cc'),
                     self._get_header_addresses_or_nil('Bcc'),
                     self._get_header_str_or_nil('In-Reply-To'),
                     self._get_header_str_or_nil('Message-Id')])

    @asyncio.coroutine
    def build_body_structure(self):
        """Build and return the body structure.

        :rtype: :class:`pymap.parsing.primitives.List`

        """
        maintype = self.message.get_content_maintype()
        subtype = self.message.get_content_subtype()
        if maintype == 'multipart':
            child_structs = yield from self.get_subparts()
            child_data = ConcatenatedParseables(
                [(yield from struct.build_body_structure())
                 for struct in child_structs])
            return List([child_data, subtype])
        params = self._get_header_params()
        id = self._get_header_str_or_nil('Content-Id')
        desc = self._get_header_str_or_nil('Content-Description')
        encoding = self._get_header_str_or_nil('Content-Transfer-Encoding')
        if maintype == 'message' and subtype == 'rfc822':
            size, lines = yield from self.get_size(True)
            child_structs = yield from self.get_subparts()
            sub_message = child_structs[0]
            sub_message_env = yield from sub_message.get_envelope_structure()
            sub_message_body = yield from sub_message.get_body_structure()
            return List([maintype, subtype, params, id, desc, encoding, size,
                         sub_message_env, sub_message_body, lines])
        elif maintype == 'text':
            size, lines = yield from self.get_size(True)
            return List([maintype, subtype, params, id, desc, encoding,
                         size, lines])
        return List([maintype, subtype, params, id, desc, encoding, size])
