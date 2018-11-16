
from typing import Tuple, Optional

from . import AString
from .. import Params, Parseable

__all__ = ['Mailbox']


class Mailbox(Parseable[str]):
    """Represents a mailbox data object from an IMAP stream.

    Args:
        mailbox: The mailbox name.

    """

    def __init__(self, mailbox: str) -> None:
        if mailbox.upper() == 'INBOX':
            mailbox = 'INBOX'
        super().__init__()
        self.mailbox = mailbox
        self._raw: Optional[bytes] = None

    @property
    def value(self) -> str:
        """The mailbox name."""
        return self.mailbox

    @classmethod
    def _modified_b64encode(cls, src: str) -> bytes:
        # Inspired by Twisted Python's implementation:
        #   https://twistedmatrix.com/trac/browser/trunk/LICENSE
        src_utf7 = src.encode('utf-7')
        return src_utf7[1:-1].replace(b'/', b',')

    @classmethod
    def _modified_b64decode(cls, src: bytes) -> str:
        # Inspired by Twisted Python's implementation:
        #   https://twistedmatrix.com/trac/browser/trunk/LICENSE
        src_utf7 = b'+%b-' % src.replace(b',', b'/')
        return src_utf7.decode('utf-7')

    @classmethod
    def encode_name(cls, mailbox: str) -> bytes:
        """Encode the mailbox name using the modified UTF-7 specification for
        IMAP.

        Args:
            mailbox: The name of the mailbox to encode.

        """
        ret = bytearray()
        is_usascii = True
        encode_start = None
        for i, symbol in enumerate(mailbox):
            charpoint = ord(symbol)
            if is_usascii:
                if charpoint == 0x26:
                    ret.extend(b'&-')
                elif 0x20 <= charpoint <= 0x7e:
                    ret.append(charpoint)
                else:
                    encode_start = i
                    is_usascii = False
            else:
                if 0x20 <= charpoint <= 0x7e:
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
    def decode_name(cls, encoded_mailbox: bytes) -> str:
        """Decode the mailbox name using the modified UTF-7 specification for
        IMAP.

        Args:
            encoded_mailbox: The encoded name of the mailbox to decode.

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
                        buf = buf[i + 1:]
                        is_usascii = True
                        break
        if not is_usascii:
            to_decode = buf.tobytes()
            decoded = cls._modified_b64decode(to_decode)
            parts.append(decoded)
        return ''.join(parts)

    @classmethod
    def parse(cls, buf: bytes, params: Params) -> Tuple['Mailbox', bytes]:
        atom, buf = AString.parse(buf, params)
        mailbox = atom.value
        if mailbox.upper() == b'INBOX':
            return cls('INBOX'), buf
        return cls(cls.decode_name(mailbox)), buf

    def __bytes__(self) -> bytes:
        if self._raw is not None:
            return self._raw
        self._raw = raw = bytes(AString(self.encode_name(self.value)))
        return raw

    def __str__(self) -> str:
        return self.value
