"""Module containing the general exceptions that may be used by pymap."""

from abc import abstractmethod, ABCMeta
from typing import Any, Optional

from .parsing.response import Response, ResponseCode, ResponseNo, ResponseOk, \
    ResponseBye

__all__ = ['ResponseError', 'NotSupportedError', 'CloseConnection',
           'CommandNotAllowed', 'SearchNotAllowed', 'InvalidAuth',
           'MailboxError', 'MailboxAbort', 'MailboxNotFound',
           'MailboxConflict', 'MailboxHasChildren', 'MailboxReadOnly',
           'AppendFailure']


class ResponseError(Exception, metaclass=ABCMeta):
    """The base exception for all custom errors that are used to generate a
    response to an IMAP command.

    """

    @abstractmethod
    def get_response(self, tag: bytes) -> Response:
        """Build an IMAP response for the error.

        Args:
            tag: The command tag that generated the error.

        """
        ...


class NotSupportedError(ResponseError, NotImplementedError):
    """Raised when an action is taken that is not supported by the server or
    backend.

    """

    def get_response(self, tag: bytes) -> ResponseNo:
        return ResponseNo(tag, b'Operation not supported.',
                          ResponseCode.of(b'CANNOT'))


class CloseConnection(ResponseError):
    """Raised when the connection should be closed immediately after sending
    the provided response.

    """

    def get_response(self, tag: bytes) -> ResponseOk:
        response = ResponseOk(tag, b'Logout successful.')
        response.add_untagged(ResponseBye(b'Logging out.'))
        return response


class CommandNotAllowed(ResponseError):
    """The command is syntactically valid, but not allowed.

    Args:
        message: The message to display in the response.
        code: Optional response code for the error.

    """

    def __init__(self, message: bytes, code: ResponseCode = None) -> None:
        super().__init__()
        self.message = message
        self.code = code

    def get_response(self, tag: bytes) -> Response:
        return ResponseNo(tag, self.message, self.code)


class SearchNotAllowed(CommandNotAllowed):
    """The ``SEARCH`` command contained a search key that could not be
    executed by the mailbox.

    Args:
        key: The search key that failed.

    """

    def __init__(self, key: bytes = None) -> None:
        command = b'SEARCH ' + key if key else b'SEARCH'
        super().__init__(command + b' not allowed.',
                         ResponseCode.of(b'CANNOT'))


class InvalidAuth(ResponseError):
    """The ``LOGIN`` or ``AUTHENTICATE`` commands received credential that the
    IMAP backend has rejected.

    """

    def __init__(self) -> None:
        super().__init__('Invalid authentication credentials.')

    def get_response(self, tag: bytes) -> ResponseNo:
        return ResponseNo(tag, str(self).encode('ascii'),
                          ResponseCode.of(b'AUTHENTICATIONFAILED'))


class MailboxError(ResponseError):
    """Parent exception for errors related to a mailbox.

    Args:
        mailbox: The name of the mailbox.
        message: The response message for the error.
        code: Optional response code for the error.

    """

    def __init__(self, mailbox: Optional[str], message: bytes,
                 code: Optional[ResponseCode] = None) -> None:
        super().__init__()
        self.mailbox = mailbox
        self.message = message
        self.code = code

    def get_response(self, tag: bytes) -> ResponseNo:
        return ResponseNo(tag, self.message, self.code)


class MailboxAbort(MailboxError):
    """An unrecoverable failure has aborted an operation on the mailbox. The
    operation may or may not succeed again.

    """

    def __init__(self) -> None:
        super().__init__(None, b'Mailbox operation aborted.',
                         ResponseCode.of(b'INUSE'))

    @classmethod
    def assertFalse(cls, cond: Any) -> None:
        """Asserts that `cond` is False.

        Args:
            cond: The condition to check.

        Raises:
            :exc:`MailboxAbort`

        """
        if cond:
            raise cls()


class MailboxNotFound(MailboxError):
    """The requested mailbox was not found.

    Args:
        mailbox: The name of the mailbox
        try_create: True if creating the mailbox first may help.

    """

    def __init__(self, mailbox: str, try_create: bool = False) -> None:
        code = ResponseCode.of(b'TRYCREATE' if try_create else b'NONEXISTENT')
        super().__init__(mailbox, b'Mailbox does not exist.', code)


class MailboxConflict(MailboxError):
    """The mailbox cannot be created or renamed because of a naming conflict
    with another mailbox.

    Args:
        mailbox: The name of the mailbox.

    """

    def __init__(self, mailbox: str) -> None:
        super().__init__(mailbox, b'Mailbox already exists.',
                         ResponseCode.of(b'ALREADYEXISTS'))


class MailboxHasChildren(MailboxError):
    """The mailbox cannot be deleted because there are other inferior
    hierarchical mailboxes below it.

    Args:
        mailbox: The name of the mailbox.

    """

    def __init__(self, mailbox: str) -> None:
        super().__init__(mailbox, b'Mailbox has inferior hierarchical names.')


class MailboxReadOnly(MailboxError):
    """The mailbox is opened read-only and the requested operation is not
    allowed.

    Args:
        mailbox: The name of the mailbox.

    """

    def __init__(self, mailbox: Optional[str] = None) -> None:
        super().__init__(mailbox, b'Mailbox is read-only.',
                         ResponseCode.of(b'READ-ONLY'))


class AppendFailure(MailboxError):
    """The mailbox append operation failed."""
