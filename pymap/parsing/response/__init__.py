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

from typing import SupportsBytes, List, Optional

from pymap.parsing.command import BadCommand
from .. import MaybeBytes

__all__ = ['ResponseCode', 'Response', 'ResponseContinuation', 'ResponseBad',
           'ResponseBadCommand', 'ResponseNo', 'ResponseOk', 'ResponseBye']


class ResponseCode(SupportsBytes):
    """Base class for response codes that may be returned along with IMAP
    server responses.

    """

    def __bytes__(self):
        raise NotImplementedError


class Response:
    """Base class for all responses sent from the server to the client. These
    responses may be sent unsolicited (e.g. idle timeouts) or in response to a
    tagged command from the client.

    :param tag: The tag bytestring of the associated command, a plus
                (``+``) to indicate a continuation requirement, or an
                asterisk (``*``) to indicate an untagged response.
    :param text: The response text.

    """

    def __init__(self, tag: MaybeBytes, text: MaybeBytes = None):
        super().__init__()
        self.tag = bytes(tag)  # type: bytes
        self.untagged = []  # type: List[Response]
        self._text = text  # type: Optional[MaybeBytes]
        self._raw = None  # type: Optional[bytes]

    @property
    def text(self):
        return bytes(self._text)

    def add_untagged(self, response: 'Response'):
        """Add an untagged response. These responses are shown before the
        parent response.

        :param response: The untagged response to add.

        """
        self.untagged.append(response)
        self._raw = None

    def add_untagged_ok(self, text: MaybeBytes, code: ResponseCode = None):
        """Add an untagged "OK" response.

        .. seealso:: :meth:`add_untagged`, :class:`ResponseOk`

        :param bytes text: The response text.
        :param code: Optional response code.

        """
        response = ResponseOk(b'*', text, code)
        self.add_untagged(response)

    def __bytes__(self):
        if self._raw is not None:
            return self._raw
        raw_lines = [bytes(data) for data in self.untagged]
        raw_lines.append(b'%b %b\r\n' % (self.tag, self.text))
        self._raw = b''.join(raw_lines)
        return self._raw


class ResponseContinuation(Response):
    """Class used for server responses that indicate a continuation
    requirement. This is when the server needs more data from the client to
    finish handling the command. The ``AUTHENTICATE`` command and any command
    that uses a literal string argument will send this response as needed.

    :param text: The continuation text.

    """

    def __init__(self, text: MaybeBytes):
        super().__init__(b'+', text)


class ConditionResponse(Response):

    condition = None  # type: bytes

    def __init__(self, tag: MaybeBytes, text: MaybeBytes,
                 code: Optional[MaybeBytes]):
        if code:
            text = b'%b %b %b' % (self.condition, code, text)
        else:
            text = b'%b %b' % (self.condition, text)
        super().__init__(tag, text)


class ResponseBad(ConditionResponse):
    """Class used for responses that indicate the server encountered a
    protocol-related error in responding to the command.

    :param bytes tag: The tag bytestring to associate the response to a
                      command.
    :param bytes text: The response text.
    :param code: Optional response code.

    """

    condition = b'BAD'

    def __init__(self, tag: MaybeBytes, text: MaybeBytes,
                 code: Optional[ResponseCode] = None):
        super().__init__(tag, text, code)


class ResponseBadCommand(ResponseBad):
    """Class used for responses that indicate the server was not able to parse
    the given command from the client. The server promises that the state of
    the connection or mailbox will not be changed as a result.

    :param exc: The exception that was raised during command parsing.
    :param code: Optional response code.

    """

    condition = b'BAD'

    def __init__(self, exc: BadCommand, code: Optional[ResponseCode] = None):
        super().__init__(exc.tag, bytes(exc), code)


class ResponseNo(ConditionResponse):
    """Response indicating the server successfully parsed the command but
    failed to execute it successfully..

    :param tag: The tag bytestring to associate the response to a command.
    :param text: The response text.
    :param code: Optional response code.

    """

    condition = b'NO'

    def __init__(self, tag: MaybeBytes, text: MaybeBytes,
                 code: Optional[ResponseCode] = None):
        super().__init__(tag, text, code)


class ResponseOk(ConditionResponse):
    """Response indicating the server successfully parsed and executed the
    command.

    :param tag: The tag bytestring to associate the response to a command.
    :param text: The response text.
    :param code: Optional response code.

    """

    condition = b'OK'

    def __init__(self, tag: MaybeBytes, text: MaybeBytes,
                 code: Optional[ResponseCode] = None):
        super().__init__(tag, text, code)


class ResponseBye(ConditionResponse):
    """Response indicating that the server will be closing the connection
    immediately after sending the response is sent. This may be sent in
    response to a command (e.g. ``LOGOUT``) or unsolicited.

    :param text: The reason for disconnection.

    """

    condition = b'BYE'

    def __init__(self, text: MaybeBytes):
        super().__init__(b'*', text, None)
