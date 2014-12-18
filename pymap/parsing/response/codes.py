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

from ..primitives import Number, List

__all__ = ['ResponseCodes', 'ResponseCode', 'Alert', 'BadCharset',
           'Capability', 'Parse', 'PermanentFlags', 'ReadOnly', 'ReadWrite',
           'TryCreate', 'UidNext', 'UidValidity', 'Unseen']


class ResponseCode(object):
    """Base class for response codes that may be returned along with IMAP
    server responses.

    """

    def __bytes__(self):
        return self.code


class Alert(ResponseCode):
    """Indicates the response text must be presented to the user in a way that
    catches attention.

    """
    code = b'ALERT'


class BadCharset(ResponseCode):
    """A ``SEARCH`` command requested an invalid charset."""
    code = b'BADCHARSET'


class Capability(ResponseCode):
    code = b'CAPABILITY'


class Parse(ResponseCode):
    """Indicates the server failed to parse the headers in a message."""
    code = b'PARSE'


class PermanentFlags(ResponseCode):
    code = b'PERMANENTFLAGS'

    def __init__(self, flags):
        super(PermanentFlags, self).__init__()
        self.flags = List(flags)

    def __bytes__(self):
        return b' '.join((self.code, bytes(self.flags)))


class ReadOnly(ResponseCode):
    """Indicates the currently selected mailbox is opened read-only."""
    code = b'READ-ONLY'


class ReadWrite(ResponseCode):
    """Indicates the currently selected mailbox is opened read-write."""
    code = b'READ-WRITE'


class TryCreate(ResponseCode):
    """Indicates that a failing ``APPEND`` or ``COPY`` command may succeed if
    the client first creates the destination mailbox.

    """
    code = b'TRYCREATE'


class UidNext(ResponseCode):
    """Indicates the next unique identifier value of the mailbox."""
    code = b'UIDNEXT'

    def __init__(self, next):
        super(UidNext, self).__init__()
        self.next = Number(next)

    def __bytes__(self):
        return b' '.join((self.code, bytes(self.next)))


class UidValidity(ResponseCode):
    """Indicates the mailbox unique identifier validity value."""
    code = b'UIDVALIDITY'

    def __init__(self, validity):
        super(UidValidity, self).__init__()
        self.validity = Number(validity)

    def __bytes__(self):
        return b' '.join((self.code, bytes(self.validity)))


class Unseen(ResponseCode):
    """Indicates the unique identifier of the first message without the
    ``\Seen`` flag.

    """
    code = b'UNSEEN'

    def __init__(self, next):
        super(Unseen, self).__init__()
        self.next = Number(next)

    def __bytes__(self):
        return b' '.join((self.code, bytes(self.next)))
