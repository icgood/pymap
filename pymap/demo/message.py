# Copyright (c) 2015 Ian C. Good
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
import email
from email.message import EmailMessage

from pymap.parsing.primitives import Number, LiteralString, List
from pymap.interfaces import MessageInterface

__all__ = ['Message']


class Message(MessageInterface):

    def __init__(self, seq, uid, flags, data):
        super().__init__(seq, uid)
        self.flags = flags
        self.data = email.message_from_bytes(data)
        self.size = len(data)

    def _get_headers(self, headers=None, inverse=False):
        ret = EmailMessage()
        for item, value in self.data.items():
            item_bytes = bytes(item, 'utf-8').upper()
            if not headers or inverse != (item_bytes in headers):
                ret[item] = value
        return bytes(ret)

    @asyncio.coroutine
    def fetch(self, attributes):
        ret = {}
        for attr in attributes:
            if attr.attribute == b'UID':
                ret[attr] = Number(self.uid)
            elif attr.attribute == b'FLAGS':
                ret[attr] = List(self.flags)
            elif attr.attribute == b'RFC822.SIZE':
                ret[attr] = Number(self.size)
            elif attr.attribute in (b'BODY.PEEK', b'BODY'):
                if attr.attribute == b'BODY.PEEK':
                    attr = attr.copy(b'BODY')
                if not attr.section[1]:
                    ret[attr] = LiteralString(bytes(self.data))
                elif attr.section[1] == b'HEADER':
                    ret[attr] = LiteralString(self._get_headers())
                elif attr.section[1] == b'HEADER.FIELDS':
                    ret[attr] = LiteralString(self._get_headers(
                        attr.section[2]))
                elif attr.section[1] == b'HEADER.FIELDS.NOT':
                    ret[attr] = LiteralString(self._get_headers(
                        attr.section[2]), True)
                elif attr.section[1] == b'TEXT':
                    ret[attr] = LiteralString(bytes(self.data))
        return ret
