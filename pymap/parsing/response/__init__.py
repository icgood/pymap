from typing import SupportsBytes, List, Optional

from ..command import BadCommand
from ..typing import MaybeBytes

__all__ = ['ResponseCode', 'Response', 'ResponseContinuation', 'ResponseBad',
           'ResponseBadCommand', 'ResponseNo', 'ResponseOk', 'ResponseBye']


class ResponseCode(SupportsBytes):
    """Base class for response codes that may be returned along with IMAP
    server responses.

    """

    def __bytes__(self) -> bytes:
        raise NotImplementedError


class Response:
    """Base class for all responses sent from the server to the client. These
    responses may be sent unsolicited (e.g. idle timeouts) or in response to a
    tagged command from the client.

    Args:
        tag: The tag bytestring of the associated command, a plus (``+``) to
            indicate a continuation requirement, or an asterisk (``*``) to
            indicate an untagged response.
        text: The response text.

    Attributes:
        tag: The tag bytestring.
        untagged: The list of added untagged responses.

    """

    def __init__(self, tag: MaybeBytes, text: MaybeBytes = None) -> None:
        super().__init__()
        self.tag = bytes(tag)
        self.untagged: List[MaybeBytes] = []
        self._text = text or b''
        self._raw: Optional[bytes] = None

    @property
    def text(self) -> bytes:
        """The response text."""
        return bytes(self._text)

    def add_untagged(self, response: MaybeBytes) -> None:
        """Add an untagged response. These responses are shown before the
        parent response.

        Args:
            response: The untagged response to add.

        """
        self.untagged.append(response)
        self._raw = None

    def add_untagged_ok(self, text: MaybeBytes,
                        code: Optional[ResponseCode] = None) -> None:
        """Add an untagged "OK" response.

        See Also:
            :meth:`.add_untagged`, :class:`ResponseOk`

        Args:
            text: The response text.
            code: Optional response code.

        """
        response = ResponseOk(b'*', text, code)
        self.add_untagged(response)

    def __bytes__(self) -> bytes:
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

    Args:
        text: The continuation text.

    """

    def __init__(self, text: MaybeBytes) -> None:
        super().__init__(b'+', text)


class ConditionResponse(Response):

    condition: Optional[bytes] = None

    def __init__(self, tag: MaybeBytes, text: MaybeBytes,
                 code: Optional[MaybeBytes]) -> None:
        if code:
            text = b'%b %b %b' % (self.condition, code, text)  # type: ignore
        else:
            text = b'%b %b' % (self.condition, text)  # type: ignore
        super().__init__(tag, text)


class ResponseBad(ConditionResponse):
    """``BAD`` response indicating the server encountered a protocol-related
    error in responding to the command.

    Args:
        tag: The tag bytestring to associate the response to a command.
        text: The response text.
        code: Optional response code.

    """

    condition = b'BAD'

    def __init__(self, tag: MaybeBytes, text: MaybeBytes,
                 code: Optional[MaybeBytes] = None) -> None:
        super().__init__(tag, text, code)


class ResponseBadCommand(ResponseBad):
    """``BAD`` response indicating the server was not able to parse the given
    command from the client. The server promises that the state of the
    connection or mailbox will not be changed as a result.

    Args:
        exc: The exception that was raised during command parsing.
        code: Optional response code.

    """

    condition = b'BAD'

    def __init__(self, exc: BadCommand, code: Optional[MaybeBytes] = None) \
            -> None:
        super().__init__(exc.tag, bytes(exc), code)


class ResponseNo(ConditionResponse):
    """``NO`` response indicating the server successfully parsed the command
    but failed to execute it successfully.

    Args:
        tag: The tag bytestring to associate the response to a command.
        text: The response text.
        code: Optional response code.

    """

    condition = b'NO'

    def __init__(self, tag: MaybeBytes, text: MaybeBytes,
                 code: Optional[MaybeBytes] = None) -> None:
        super().__init__(tag, text, code)


class ResponseOk(ConditionResponse):
    """``OK`` response indicating the server successfully parsed and executed
    the command.

    Args:
        tag: The tag bytestring to associate the response to a command.
        text: The response text.
        code: Optional response code.

    """

    condition = b'OK'

    def __init__(self, tag: MaybeBytes, text: MaybeBytes,
                 code: Optional[MaybeBytes] = None) -> None:
        super().__init__(tag, text, code)


class ResponseBye(ConditionResponse):
    """``BYE`` response indicating that the server will be closing the
    connection immediately after sending the response is sent. This may be sent
    in response to a command (e.g. ``LOGOUT``) or unsolicited.

    Args:
        text: The reason for disconnection.

    """

    condition = b'BYE'

    def __init__(self, text: MaybeBytes) -> None:
        super().__init__(b'*', text, None)
