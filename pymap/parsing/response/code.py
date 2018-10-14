# Copyright (c) 2018 Ian C. Good
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

from typing import Iterable, Optional, Sequence

from . import ResponseCode, Response
from ..primitives import ListP
from ..typing import MaybeBytes

__all__ = ['Alert', 'BadCharset', 'Capability', 'Parse',
           'PermanentFlags', 'ReadOnly', 'ReadWrite', 'TryCreate', 'UidNext',
           'UidValidity', 'Unseen']


class Alert(ResponseCode):
    """Indicates the response text must be presented to the user in a way that
    catches attention.

    """

    def __bytes__(self):
        return b'[ALERT]'


class BadCharset(ResponseCode):
    """A ``SEARCH`` command requested an invalid charset."""

    def __bytes__(self):
        return b'[BADCHARSET]'


class Capability(ResponseCode):
    """Lists the capabilities the server advertises to the client."""

    def __init__(self, server_capabilities: Iterable[MaybeBytes]) -> None:
        super().__init__()
        self.capabilities = [bytes(cap) for cap in server_capabilities]
        self._raw: Optional[bytes] = None

    @property
    def string(self) -> bytes:
        if self._raw is not None:
            return self._raw
        self._raw = raw = b' '.join(
            [b'CAPABILITY', b'IMAP4rev1'] + self.capabilities)  # type: ignore
        return raw

    def __contains__(self, capability: MaybeBytes) -> bool:
        return capability in self.capabilities

    def to_response(self) -> Response:
        return Response(b'*', self.string)

    def __bytes__(self):
        return b'[%b]' % self.string


class Parse(ResponseCode):
    """Indicates the server failed to parse the headers in a message."""

    def __bytes__(self):
        return b'[PARSE]'


class PermanentFlags(ResponseCode):

    def __init__(self, flags: Iterable[MaybeBytes]) -> None:
        super().__init__()
        self.flags: Sequence[MaybeBytes] = sorted(flags)
        self._raw = b'[PERMANENTFLAGS %b]' % ListP(self.flags)  # type: ignore

    def __bytes__(self):
        return self._raw


class ReadOnly(ResponseCode):
    """Indicates the currently selected mailbox is opened read-only."""

    def __bytes__(self):
        return b'[READ-ONLY]'


class ReadWrite(ResponseCode):
    """Indicates the currently selected mailbox is opened read-write."""

    def __bytes__(self):
        return b'[READ-WRITE]'


class TryCreate(ResponseCode):
    """Indicates that a failing ``APPEND`` or ``COPY`` command may succeed if
    the client first creates the destination mailbox.

    """

    def __bytes__(self):
        return b'[TRYCREATE]'


class UidNext(ResponseCode):
    """Indicates the next unique identifier value of the mailbox."""

    def __init__(self, next_: int) -> None:
        super().__init__()
        self.next = next_
        self._raw = b'[UIDNEXT %i]' % next_

    def __bytes__(self):
        return self._raw


class UidValidity(ResponseCode):
    """Indicates the mailbox unique identifier validity value."""

    def __init__(self, validity: int) -> None:
        super().__init__()
        self.validity = validity
        self._raw = b'[UIDVALIDITY %i]' % validity

    def __bytes__(self):
        return self._raw


class Unseen(ResponseCode):
    """Indicates the unique identifier of the first message without the
    ``\\Seen`` flag.

    """

    def __init__(self, next_: int) -> None:
        super().__init__()
        self.next = next_
        self._raw = b'[UNSEEN %i]' % next_

    def __bytes__(self):
        return self._raw
