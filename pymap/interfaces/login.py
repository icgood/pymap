from typing import TYPE_CHECKING, Optional

from pysasl import AuthenticationCredentials

from .session import SessionInterface

__all__ = ['LoginProtocol']

if TYPE_CHECKING:
    from typing_extensions import Protocol
else:
    class Protocol:
        pass


class LoginProtocol(Protocol):
    """Defines the callback protocol that backends use to initialize a new
    session.

    """

    async def __call__(self, credentials: AuthenticationCredentials) \
            -> Optional[SessionInterface]:
        """Given a set of authentication credentials, initialize a new IMAP
        session for the user.

        Args:
            credentials: Authentication credentials supplied by the user.

        Returns:
            The new IMAP session, or ``None`` if the credentials were invalid.

        """
        ...
