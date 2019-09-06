"""Implements the modified UTF-7 specification used for encoding and decoding
mailbox names in IMAP.

See Also:
    `RFC 3501 5.1.3 <https://tools.ietf.org/html/rfc3501#section-5.1.3>`_

"""

from __future__ import annotations

__all__ = ['modutf7_encode', 'modutf7_decode']


def _modified_b64encode(src: str) -> bytes:
    # Inspired by Twisted Python's implementation:
    #   https://twistedmatrix.com/trac/browser/trunk/LICENSE
    src_utf7 = src.encode('utf-7')
    return src_utf7[1:-1].replace(b'/', b',')


def _modified_b64decode(src: bytes) -> str:
    # Inspired by Twisted Python's implementation:
    #   https://twistedmatrix.com/trac/browser/trunk/LICENSE
    src_utf7 = b'+%b-' % src.replace(b',', b'/')
    return src_utf7.decode('utf-7')


def modutf7_encode(data: str) -> bytes:
    """Encode the string using modified UTF-7.

    Args:
        data: The input string to encode.

    """
    ret = bytearray()
    is_usascii = True
    encode_start = None
    for i, symbol in enumerate(data):
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
                to_encode = data[encode_start:i]
                encoded = _modified_b64encode(to_encode)
                ret.append(0x26)
                ret.extend(encoded)
                ret.extend((0x2d, charpoint))
                is_usascii = True
    if not is_usascii:
        to_encode = data[encode_start:]
        encoded = _modified_b64encode(to_encode)
        ret.append(0x26)
        ret.extend(encoded)
        ret.append(0x2d)
    return bytes(ret)


def modutf7_decode(data: bytes) -> str:
    """Decode the bytestring using modified UTF-7.

    Args:
        data: The encoded bytestring to decode.

    """
    parts = []
    is_usascii = True
    buf = memoryview(data)
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
                    decoded = _modified_b64decode(to_decode)
                    parts.append(decoded)
                    buf = buf[i + 1:]
                    is_usascii = True
                    break
    if not is_usascii:
        to_decode = buf.tobytes()
        decoded = _modified_b64decode(to_decode)
        parts.append(decoded)
    return ''.join(parts)
