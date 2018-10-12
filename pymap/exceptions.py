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

"""Module containing the exceptions that may be used by pymap plugins."""

from typing import Optional

from .parsing.response import Response, ResponseCode, ResponseNo, ResponseOk, \
    ResponseBye
from .parsing.response.code import TryCreate, ReadOnly

__all__ = ['ResponseError', 'CloseConnection', 'MailboxNotFound',
           'MailboxConflict', 'MailboxHasChildren', 'MailboxReadOnly',
           'AppendFailure']


class ResponseError(Exception):
    """The base exception for all custom errors that are used to generate a
    response to an IMAP command.

    """

    def get_response(self, tag: bytes) -> Response:
        """Build an IMAP response for the error.

        :param tag: The command tag that generated the error.

        """
        raise NotImplementedError


class CloseConnection(ResponseError):
    """Raised when the connection should be closed immediately after sending
    the provided response.

    """

    def get_response(self, tag: bytes) -> ResponseOk:
        response = ResponseOk(tag, b'Logout successful.')
        response.add_untagged(ResponseBye(b'Logging out.'))
        return response


class MailboxError(ResponseError):
    """Parent exception for errors related to a mailbox.

    :param mailbox: The name of the mailbox.
    :param message: The response message for the error.
    :param code: Optional response code for the error.

    """

    def __init__(self, mailbox: str, message: bytes,
                 code: Optional[ResponseCode] = None) -> None:
        super().__init__()
        self.mailbox = mailbox
        self.message = message
        self.code = code

    def get_response(self, tag: bytes) -> ResponseNo:
        return ResponseNo(tag, self.message, self.code)


class MailboxNotFound(MailboxError):
    """The requested mailbox was not found.

    :param mailbox: The name of the mailbox
    :param try_create: Whether to include ``[TRYCREATE]`` in the error.

    """

    def __init__(self, mailbox: str, try_create: bool = False) -> None:
        super().__init__(mailbox, b'Mailbox does not exist.',
                         TryCreate() if try_create else None)


class MailboxConflict(MailboxError):
    """The mailbox cannot be created or renamed because of a naming conflict
    with another mailbox.

    :param mailbox: The name of the mailbox.

    """

    def __init__(self, mailbox: str) -> None:
        super().__init__(mailbox, b'Mailbox already exists.')


class MailboxHasChildren(MailboxError):
    """The mailbox cannot be deleted because there are other inferior
    heirarchical mailboxes below it.

    :param mailbox: The name of the mailbox.

    """

    def __init__(self, mailbox: str) -> None:
        super().__init__(mailbox, b'Mailbox has inferior hierarchical names.')


class MailboxReadOnly(MailboxError):
    """The mailbox is opened read-only and the requested operation is not
    allowed.

    :param mailbox: The name of the mailbox.

    """

    def __init__(self, mailbox: str) -> None:
        super().__init__(mailbox, b'Mailbox is read-only.', ReadOnly())


class AppendFailure(MailboxError):
    """The mailbox append operation failed."""
    pass
