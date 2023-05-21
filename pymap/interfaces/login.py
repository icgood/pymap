
from __future__ import annotations

from abc import abstractmethod
from contextlib import AbstractAsyncContextManager
from datetime import datetime
from typing import Protocol

from pysasl.creds.server import ServerCredentials

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
    async def authenticate(self, credentials: ServerCredentials) \
            -> IdentityInterface:
        """Authenticate the credentials.

        Args:
            credentials: Authentication credentials supplied by the user.

        Raises:
            :exc:`~pymap.exceptions.InvalidAuth`

        """
        ...

    @abstractmethod
    async def authorize(self, authenticated: IdentityInterface, authzid: str) \
            -> IdentityInterface:
        """The *authenticated* identity must be authorized to assume the
        identity of *authzid*, returning its user identity if successful.

        Args:
            authenticated: The identity that successfully authorized.
            authzid: The identity name to be authorized.

        Raises:
            :exc:`~pymap.exceptions.AuthorizationFailure`

        """
        ...


class IdentityInterface(Protocol):
    """Defines the operations available to a user identity. This user identity
    may or may not "exist" yet in the backend.

    """

    @property
    @abstractmethod
    def name(self) -> str:
        """The SASL authorization identity of the user."""
        ...

    @property
    @abstractmethod
    def roles(self) -> frozenset[str]:
        """The set of roles granted to this identity."""
        ...

    @abstractmethod
    def new_session(self) -> AbstractAsyncContextManager[SessionInterface]:
        """Returns a new IMAP session.

        Raises:
            :class:`~pymap.exceptions.UserNotFound`
            :exc:`~pymap.exceptions.NotAllowedError`

        """
        ...

    @abstractmethod
    async def new_token(self, *, expiration: datetime | None = None) \
            -> str | None:
        """Returns a bearer token that may be used in future authentication
        attempts.

        Since tokens should use their own private key, backends may return
        ``None`` if it does not support tokens or the user does not have a
        private key.

        Args:
            expiration: When the token should stop being valid.

        Raises:
            :exc:`~pymap.exceptions.UserNotFound`
            :exc:`~pymap.exceptions.NotAllowedError`

        """
        ...

    @abstractmethod
    async def get(self) -> UserMetadata:
        """Return the metadata associated with the user identity.

        Raises:
            :exc:`~pymap.exceptions.UserNotFound`
            :exc:`~pymap.exceptions.NotAllowedError`

        """
        ...

    @abstractmethod
    async def set(self, metadata: UserMetadata) -> int | None:
        """Assign new metadata to the user identity.

        Args:
            metadata: New metadata, such as password.

        Returns:
            The :attr:`~pymap.user.UserMetadata.entity_tag` of the updated
            metadata, if applicable.

        Raises:
            :exc:`~pymap.exceptions.CannotReplaceUser`
            :exc:`~pymap.exceptions.NotAllowedError`

        """
        ...

    @abstractmethod
    async def delete(self) -> None:
        """Delete existing metadata for the user identity.

        Raises:
            :exc:`~pymap.exceptions.UserNotFound`
            :exc:`~pymap.exceptions.NotAllowedError`

        """
        ...
