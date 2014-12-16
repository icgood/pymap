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

from . import Parseable
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
    def _modified_b64encode(cls, src):
        # Inspired by Twisted Python's implementation:
        #   https://twistedmatrix.com/trac/browser/trunk/LICENSE
        src_utf7 = src.encode('utf-7')
        return src_utf7[1:-1].replace(b'/', b',')

    @classmethod
    def _modified_b64decode(cls, src):
        # Inspired by Twisted Python's implementation:
        #   https://twistedmatrix.com/trac/browser/trunk/LICENSE
        src_utf7 = b'+' + src.replace(b',', b'/') + b'-'
        return src_utf7.decode('utf-7')

    @classmethod
    def encode_name(cls, mailbox):
        """Encode the mailbox name using the modified UTF-7 specification for
        IMAP.

        :param str mailbox: The name of the mailbox to encode.
        :rtype: bytes

        """
        ret = bytearray()
        is_usascii = True
        for i, symbol in enumerate(mailbox):
            charpoint = ord(symbol)
            if is_usascii:
                if charpoint == 0x26:
                    ret.extend(b'&-')
                elif charpoint >= 0x20 and charpoint <= 0x7e:
                    ret.append(charpoint)
                else:
                    encode_start = i
                    is_usascii = False
            else:
                if charpoint >= 0x20 and charpoint <= 0x7e:
                    to_encode = mailbox[encode_start:i]
                    encoded = cls._modified_b64encode(to_encode)
                    ret.append(0x26)
                    ret.extend(encoded)
                    ret.extend((0x2d, charpoint))
                    is_usascii = True
        if not is_usascii:
            to_encode = mailbox[encode_start:]
            encoded = cls._modified_b64encode(to_encode)
            ret.append(0x26)
            ret.extend(encoded)
            ret.append(0x2d)
        return bytes(ret)

    @classmethod
    def decode_name(cls, encoded_mailbox):
        """Decode the mailbox name using the modified UTF-7 specification for
        IMAP.

        :param bytes encoded_mailbox: The encoded name of the mailbox to
                                      decode.
        :rtype: str

        """
        parts = []
        is_usascii = True
        buf = memoryview(encoded_mailbox)
        while buf:
            byte = buf[0]
            if is_usascii:
                if buf[0:2] == b'&-':
                    parts.append('&')
                    buf = buf[2:]
                elif byte == 0x26:
                    is_usascii = False
                    buf = buf[1:]
                else:
                    parts.append(chr(byte))
                    buf = buf[1:]
            else:
                for i, byte in enumerate(buf):
                    if byte == 0x2d:
                        to_decode = buf[:i].tobytes()
                        decoded = cls._modified_b64decode(to_decode)
                        parts.append(decoded)
                        buf = buf[i+1:]
                        is_usascii = True
                        break
        if not is_usascii:
            to_decode = buf.tobytes()
            decoded = cls._modified_b64decode(to_decode)
            parts.append(decoded)
        return ''.join(parts)

    @classmethod
    def parse(cls, buf, **kwargs):
        buf = memoryview(buf)
        atom, buf = Atom.parse(buf)
        mailbox = atom.value
        if mailbox.upper() == b'INBOX':
            return cls('INBOX'), buf
        return cls(cls.decode_name(mailbox)), buf

    def __bytes__(self):
        return self.encode_name(self.value)
