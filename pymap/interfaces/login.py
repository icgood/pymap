
from __future__ import annotations

from abc import abstractmethod, ABCMeta
from collections.abc import Mapping, Set
from contextlib import AbstractAsyncContextManager
from datetime import datetime
from typing import Protocol

from pysasl.creds.server import ServerCredentials
from pysasl.identity import Identity

from .session import SessionInterface
from .token import TokensInterface

__all__ = ['LoginInterface', 'IdentityInterface', 'UserInterface']


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
        """Authenticate and authorize the credentials.

        Args:
            credentials: Authentication credentials supplied by the user.

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
    async def new_token(self, *, expiration: datetime | None = None) \
            -> str | None:
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
    async def get(self) -> UserInterface:
        """Return the metadata associated with the user identity.

        Raises:
            :exc:`~pymap.exceptions.UserNotFound`

        """
        ...

    @abstractmethod
    async def set(self, metadata: UserInterface) -> None:
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


class UserInterface(Identity, metaclass=ABCMeta):
    """Contains information about a user."""

    @property
    @abstractmethod
    def password(self) -> str | None:
        """The password string or hash digest."""
        ...

    @property
    @abstractmethod
    def roles(self) -> Set[str]:
        """A set of role strings given to the user. These strings only have
        meaning to the backend.

        """
        ...

    @property
    @abstractmethod
    def params(self) -> Mapping[str, str]:
        """Metadata parameters associated with the user."""
        ...

    @abstractmethod
    def get_key(self, identifier: str) -> bytes | None:
        """Find the token key for the given identifier associated with this
        user.

        Args:
            identifier: Any string that can facilitate the lookup of the key.

        """
        ...

    @abstractmethod
    async def check_password(self, creds: ServerCredentials) -> None:
        """Check the given credentials against the known password comparison
        data. If the known data used a hash, then the equivalent hash of the
        provided secret is compared.

        Args:
            creds: The provided authentication credentials.
            token_key: The token key bytestring.

        Raises:
            :class:`~pymap.exceptions.InvalidAuth`

        """
        ...
