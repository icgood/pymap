
from __future__ import annotations

from abc import abstractmethod
from collections.abc import Set
from datetime import datetime
from typing import Optional, Protocol

from pysasl.creds import AuthenticationCredentials

__all__ = ['TokensInterface']


class TokensInterface(Protocol):
    """Defines the create and parse operations for a token type."""

    @abstractmethod
    def get_login_token(self, identifier: str, key: bytes, *,
                        authzid: str = None, location: str = None,
                        expiration: datetime = None) -> Optional[str]:
        """Returns a new token string that encapsulates the provided login
        data, or ``None`` if tokens are not supported.

        Args:
            identifier: Any string that can facilitate the lookup of *key*.
            key: The private key used to create and verify the token.
            authzid: Limits the token to authorizing as this identity.
            location: Arbitrary metadata string, application-specific.
            expiration: An expiration when this token shall no longer be valid.

        """
        ...

    @abstractmethod
    def get_admin_token(self, admin_key: Optional[bytes], *,
                        authzid: str = None, location: str = None,
                        expiration: datetime = None) -> Optional[str]:
        """Returns a new token string that encapsulates the provided login
        data, or ``None`` if tokens are not supported. This token uses a
        special private admin key that grants unrestricted access.

        Args:
            admin_key: The private admin key.
            authzid: Limits the token to authorizing as this identity.
            location: Arbitrary metadata string, application-specific.
            expiration: An expiration when this token shall no longer be valid.

        """
        ...

    @abstractmethod
    def parse(self, authzid: str, token: str, *,
              admin_keys: Set[bytes] = ...) -> AuthenticationCredentials:
        """Parses a token string to produce authentication credentials.

        Args:
            authzid: Check token for authorization to this identity.
            token: The token string.
            admin_keys: The set of possible private admin keys.

        Raises:
            ValueError: The *token* string was not valid.

        """
        ...
