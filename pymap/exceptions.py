"""Module containing the general exceptions that may be used by pymap."""

from __future__ import annotations

from abc import abstractmethod, ABCMeta
from typing import Optional

from .parsing.specials import SearchKey
from .parsing.response import Response, ResponseCode, ResponseNo, ResponseOk, \
    ResponseBye

__all__ = ['ResponseError', 'CloseConnection', 'NotSupportedError',
           'TemporaryFailure', 'SearchNotAllowed', 'InvalidAuth',
           'AuthorizationFailure', 'NotAllowedError', 'IncompatibleData',
           'MailboxError', 'MailboxNotFound', 'MailboxConflict',
           'MailboxHasChildren', 'MailboxReadOnly', 'AppendFailure',
           'UserNotFound']


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


class CloseConnection(ResponseError):
    """Raised when the connection should be closed immediately after sending
    the provided response.

    """

    def get_response(self, tag: bytes) -> ResponseOk:
        response = ResponseOk(tag, b'Logout successful.')
        response.add_untagged(ResponseBye(b'Logging out.'))
        return response


class NotSupportedError(ResponseError, NotImplementedError):
    """Raised when an action is taken that might be syntactically valid, but is
    not supported by the server or backend.

    """

    def __init__(self, msg: str = 'Operation not supported.') -> None:
        super().__init__(msg)
        self._raw = msg.encode('utf-8')

    def get_response(self, tag: bytes) -> ResponseNo:
        return ResponseNo(tag, self._raw, ResponseCode.of(b'CANNOT'))


class SearchNotAllowed(NotSupportedError):
    """The ``SEARCH`` command contained a search key that could not be
    executed by the mailbox.

    Args:
        key: The search key that failed.

    """

    def __init__(self, key: SearchKey) -> None:
        super().__init__(f'SEARCH {key.value_str} not supported.')


class InvalidAuth(ResponseError):
    """The ``LOGIN`` or ``AUTHENTICATE`` commands received credentials that the
    IMAP backend has rejected.

    """

    def __init__(self, msg: str = 'Invalid authentication credentials.') \
            -> None:
        super().__init__(msg)
        self._raw = msg.encode('utf-8')

    def get_response(self, tag: bytes) -> ResponseNo:
        return ResponseNo(tag, self._raw,
                          ResponseCode.of(b'AUTHENTICATIONFAILED'))


class AuthorizationFailure(InvalidAuth):
    """The credentials in ``LOGIN`` or ``AUTHENTICATE`` were authenticated but
    failed to authorize as the requested identity.

    """

    def __init__(self, msg: str = 'Authorization failed.') -> None:
        super().__init__(msg)

    def get_response(self, tag: bytes) -> ResponseNo:
        return ResponseNo(tag, self._raw,
                          ResponseCode.of(b'AUTHORIZATIONFAILED'))


class NotAllowedError(ResponseError):
    """The operation is not allowed due to access controls."""

    def __init__(self, msg: str = 'Operation not allowed.') -> None:
        super().__init__(msg)
        self._raw = msg.encode('utf-8')

    def get_response(self, tag: bytes) -> ResponseNo:
        return ResponseNo(tag, self._raw, ResponseCode.of(b'NOPERM'))


class IncompatibleData(InvalidAuth):
    """The ``LOGIN`` or ``AUTHENTICATE`` command could not succeed because the
    detected mailbox data was not in a compatible format.

    """

    def __init__(self, msg: str = 'Incompatible mailbox data.') -> None:
        super().__init__(msg)


class TemporaryFailure(ResponseError):
    """The operation failed, but may succeed if tried again. The ``[INUSE]``
    response code is added to the response.

    """

    def __init__(self, msg: str) -> None:
        super().__init__(msg)
        self._raw = msg.encode('utf-8')

    def get_response(self, tag: bytes) -> ResponseNo:
        return ResponseNo(tag, self._raw, ResponseCode.of(b'INUSE'))


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


class MailboxNotFound(MailboxError):
    """The requested mailbox was not found.

    Args:
        mailbox: The name of the mailbox
        try_create: True if creating the mailbox first may help.

    """

    def __init__(self, mailbox: str, *, try_create: bool = False) -> None:
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


class UserNotFound(ResponseError):
    """The requested user was not found."""

    def get_response(self, tag: bytes) -> ResponseNo:
        return ResponseNo(tag, b'User not found.',
                          ResponseCode.of(b'NONEXISTENT'))
