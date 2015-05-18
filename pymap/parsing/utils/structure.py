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

from email.charset import Charset
from email.utils import getaddresses

from ..primitives import *  # NOQA

__all__ = ['EnvelopeStructure', 'BodyStructure']


class EnvelopeStructure(object):
    """Given a :class:`email.message.Message`-like object, pull the headers
    necessary to construct an envelope structure, as described in `RFC 3501
    2.3.5. <https://tools.ietf.org/html/rfc3501#section-2.3.5>`_.

    :param message: The message object to generate the envelope structure for.
    :type message: :class:`~email.message.Message`

    """

    _HEADER_CHARSET = Charset('utf-8')

    def __init__(self, message):
        super().__init__()
        self.message = message
        self._raw = None

    @classmethod
    def _header_encode(value):
        try:
            return QuotedString(bytes(value, 'ascii'))
        except UnicodeEncodeError:
            value_encoded = _HEADER_CHARSET.header_encode(value)
            return QuotedString(bytes(value_encoded, 'ascii'))

    def _get_header_str_or_nil(self, name):
        value = message.get(name)
        if not value:
            return Nil()
        return _header_encode(value)

    def _get_header_addresses_or_nil(self, name, default_name=None):
        values = message.get_all(name)
        if not values:
            if default_name:
                values = message.get_all(default_name)
            if not values:
                return Nil()
        ret = []
        for realname, address in getaddresses(values):
            realname = _header_encode(realname)
            localpart, _, domain = address.rpartition('@')
            localpart = _header_encode(localpart)
            domain = _header_encode(domain)
            ret.append(List([realname, Nil(), localpart, domain]))
        return List(ret)

    def _generate(self):
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

    def __bytes__(self):
        if self._raw is not None:
            return self._raw
        self._raw = raw = self._generate()
        return raw


class BodyStructure(object):
    """Given a :class:`email.message.Message`-like object, examine the MIME
    structure to construct a body structure, as described in `RFC 3501
    2.3.6. <https://tools.ietf.org/html/rfc3501#section-2.3.6>`_.

    :param message: The message object to generate the body structure for.
    :type message: :class:`~email.message.Message`

    """
    pass
