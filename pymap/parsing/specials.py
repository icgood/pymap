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

import re
import base64

from . import Parseable, NotParseable
from .primitives import Atom

__all__ = ['Special', 'Mailbox']


class Special(Parseable):
    """Base class for special data objects in an IMAP stream.

    """
    pass


class Mailbox(Special):
    """Represents a mailbox data object from an IMAP stream.

    :param str mailbox: The mailbox string.

    """

    def __init__(self, mailbox):
        super(Mailbox, self).__init__()
        self.value = mailbox

    @classmethod
    def parse(cls, buf, **kwargs):
        buf = memoryview(buf)
        atom, buf = Atom.parse(buf)
        mailbox = atom.value
        if mailbox.upper() == b'INBOX':
            return cls('INBOX'), buf
        return cls(str(mailbox, errors='ignore')), buf

    def __bytes__(self):
        return bytes(self.value, 'utf-8')
