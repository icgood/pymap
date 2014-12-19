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

__all__ = ['Response', 'ResponseContinuation', 'ResponseBad',
           'ResponseBadCommand', 'ResponseNo', 'ResponseOk', 'ResponseBye']


class Response(object):
    """Base class for all responses sent from the server to the client. These
    responses may be sent unsolicited (e.g. idle timeouts) or in response to a
    tagged command from the client.

    :param bytes tag: The tag bytestring of the associated command, a plus
                      (``+``) to indicate a continuation requirement, or an
                      asterisk (``*``) to indicate an untagged response.
    :param bytes text: The response text.

    """

    def __init__(self, tag, text):
        super(Response, self).__init__()
        self.tag = bytes(tag)
        self.text = bytes(text)
        self.data = []
        self._raw = None

    @asyncio.coroutine
    def send_stream(self, writer):
        writer.write(bytes(self))
        yield from writer.drain()

    def add_data(self, response):
        self.data.append(response)

    def __bytes__(self):
        if self._raw is not None:
            return self._raw
        raw_lines = [bytes(data) for data in self.data]
        raw_lines.append(b''.join((self.tag, b' ', self.text, b'\r\n')))
        self._raw = b''.join(raw_lines)
        return self._raw


class ResponseContinuation(Response):
    """Class used for server responses that indicate a continuation
    requirement. This is when the server needs more data from the client to
    finish handling the command. The ``AUTHENTICATE`` command and any command
    that uses a literal string argument will send this response as needed.

    :param bytes text: The continuation text.

    """

    def __init__(self, text):
        super(ResponseContinuation, self).__init__(b'+', text)


class ConditionResponse(Response):

    def __init__(self, tag, text, code):
        if code:
            text = b' '.join((self.condition, bytes(code), text))
        else:
            text = b' '.join((self.condition, text))
        super(ConditionResponse, self).__init__(tag, text)



class ResponseBad(ConditionResponse):
    """Class used for responses that indicate the server encountered a
    protocol-related error in responding to the command.

    :param bytes tag: The tag bytestring to associate the response to a
                      command.
    :param bytes text: The response text.
    :param code: Optional response code.
    :type code: :class:`~pymap.parsing.response.codes.ResponseCode`

    """

    condition = b'BAD'

    def __init__(self, tag, text, code=None):
        super(ResponseBad, self).__init__(tag, text, code)


class ResponseBadCommand(ResponseBad):
    """Class used for responses that indicate the server was not able to parse
    the given command from the client. The server promises that the state of
    the connection or mailbox will not be changed as a result.

    :param exc: The  exception that was raised during command parsing.
    :type exc: :exc:`~pymap.parsing.command.BadCommand`
    :param code: Optional response code.
    :type code: :class:`~pymap.parsing.response.codes.ResponseCode`

    """

    condition = b'BAD'

    def __init__(self, exc, code=None):
        super(ResponseBad, self).__init__(exc.tag, bytes(exc), code)


class ResponseNo(ConditionResponse):
    """Response indicating the server successfully parsed the command but
    failed to execute it successfully..

    :param bytes tag: The tag bytestring to associate the response to a
                      command.
    :param bytes text: The response text.
    :param code: Optional response code.
    :type code: :class:`~pymap.parsing.response.codes.ResponseCode`

    """

    condition = b'NO'

    def __init__(self, tag, text, code=None):
        super(ResponseNo, self).__init__(tag, text, code)


class ResponseOk(ConditionResponse):
    """Response indicating the server successfully parsed and executed the
    command.

    :param bytes tag: The tag bytestring to associate the response to a
                      command.
    :param bytes text: The response text.
    :param code: Optional response code.
    :type code: :class:`~pymap.parsing.response.codes.ResponseCode`

    """

    condition = b'OK'

    def __init__(self, tag, text, code=None):
        super(ResponseOk, self).__init__(tag, text, code)


class ResponseBye(ConditionResponse):
    """Response indicating that the server will be closing the connection
    immediately after sending the response is sent. This may be sent in
    response to a command (e.g. ``LOGOUT``) or unsolicited.

    :param bytes text: The reason for disconnection.

    """

    condition = b'BYE'

    def __init__(self, text):
        super(ResponseBye, self).__init__(b'*', text, None)
