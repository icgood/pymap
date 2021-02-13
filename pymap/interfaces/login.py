
from __future__ import annotations

from abc import abstractmethod
from contextlib import AbstractAsyncContextManager
from datetime import datetime
from typing import Optional, Protocol

from pysasl import AuthenticationCredentials

from .session import SessionInterface
from .token import TokensInterface
from ..user import UserMetadata

__all__ = ['LoginInterface', 'IdentityInterface']


class LoginInterface(Protocol):
    """Defines the authentication operations for backends."""

    @property
    @abstractmethod
    def tokens(self) -> TokensInterface:
        """Handles creation and authentication of bearer tokens."""
        ...

    @abstractmethod
    async def authenticate(self, credentials: AuthenticationCredentials) \
            -> IdentityInterface:
        """Authenticate and authorize the credentials.

        Raises:
            :exc:`~pymap.exceptions.InvalidAuth`

        """
        ...


class IdentityInterface(Protocol):
    """Defines the operations available to a user identity that has been
    authenticated and authorized. This user identity may or may not "exist" in
    the backend.

    """

    @property
    def name(self) -> str:
        """The SASL authorization identity of the logged-in user."""
        ...

    @abstractmethod
    def new_session(self) -> AbstractAsyncContextManager[SessionInterface]:
        """Authenticate and authorize the credentials, returning a new IMAP
        session.

        Args:
            credentials: Authentication credentials supplied by the user.

        Raises:
            :class:`~pymap.exceptions.UserNotFound`

        """
        ...

    @abstractmethod
    async def new_token(self, *, expiration: datetime = None) -> Optional[str]:
        """Authenticate and authorize the credentials, returning a bearer token
        that may be used in future authentication attempts.

        Since tokens should use their own private key, backends may return
        ``None`` if it does not support tokens or the user does not have a
        private key.

        Args:
            expiration: When the token should stop being valid.

        Raises:
            :exc:`~pymap.exceptions.UserNotFound`

        """
        ...

    @abstractmethod
    async def get(self) -> UserMetadata:
        """Return the metadata associated with the user identity.

        Raises:
            :exc:`~pymap.exceptions.UserNotFound`

        """
        ...

    @abstractmethod
    async def set(self, metadata: UserMetadata) -> None:
        """Assign new metadata to the user identity.

        Args:
            metadata: New metadata, such as password.

        """
        ...

    @abstractmethod
    async def delete(self) -> None:
        """Delete existing metadata for the user identity.

        Raises:
            :exc:`~pymap.exceptions.UserNotFound`

        """
        ...
