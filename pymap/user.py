
from __future__ import annotations

from collections.abc import Mapping
from typing import Optional, Final

from pysasl.creds import StoredSecret, AuthenticationCredentials

from .config import IMAPConfig
from .exceptions import InvalidAuth

__all__ = ['UserMetadata']


class UserMetadata:
    """Contains user metadata such as the password or hash.

    Args:
        config: The configuration object.
        password: The password string or hash digest.
        params: Metadata parameters associated with the user.

    """

    def __init__(self, config: IMAPConfig, *, password: str = None,
                 **params: Optional[str]) -> None:
        super().__init__()
        self.config: Final = config
        self.password: Final = password
        self.params: Final = {key: val for key, val in params.items()
                              if val is not None}

    @property
    def role(self) -> Optional[str]:
        """The value of the ``role`` key from *params*."""
        return self.params.get('role')

    def to_dict(self, **extra: str) -> Mapping[str, str]:
        """Combines the *password*, *params*, and *extra* into a dictionary.

        Args:
            extra: Additional parameters as keyword arguments, which will be
                merged into the result.

        """
        ret = dict(self.params, **extra)
        if self.password is not None:
            ret['password'] = self.password
        return ret

    async def check_password(self, creds: AuthenticationCredentials, *,
                             token_key: bytes = None) -> None:
        """Check the given credentials against the known password comparison
        data. If the known data used a hash, then the equivalent hash of the
        provided secret is compared.

        Args:
            creds: The provided authentication credentials.
            token_key: The token key bytestring.

        Raises:
            :class:`~pymap.exceptions.InvalidAuth`

        """
        hash_context = self.config.hash_context
        cpu_subsystem = self.config.cpu_subsystem
        stored_secret: Optional[StoredSecret] = None
        if self.password is not None:
            stored_secret = StoredSecret(self.password, hash=hash_context)
        fut = self._check_secret(creds, stored_secret, token_key)
        if not await cpu_subsystem.execute(fut):
            raise InvalidAuth()

    async def _check_secret(self, creds: AuthenticationCredentials,
                            stored_secret: Optional[StoredSecret],
                            key: Optional[bytes]) -> bool:
        return creds.check_secret(stored_secret, key=key)
