
from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping, MutableSet
from typing import Final

from pysasl.creds.server import ServerCredentials
from pysasl.hashing import Cleartext
from pysasl.identity import Identity

from .config import IMAPConfig
from .exceptions import InvalidAuth

__all__ = ['UserRoles', 'UserMetadata']


class UserRoles(MutableSet[str]):
    """A set of roles for a user.

    Args:
        roles: Initial roles for the set.

    """

    __slots__ = ['_roles']

    def __init__(self, /, roles: Iterable[str | None] = ()) -> None:
        super().__init__()
        self._roles: set[str] = set(role for role in roles if role is not None)

    def __contains__(self, role: object) -> bool:
        return role in self._roles

    def __iter__(self) -> Iterator[str]:
        return iter(self._roles)

    def __len__(self) -> int:
        return len(self._roles)

    def add(self, role: str | None) -> None:
        if role is not None:
            self._roles.add(role)

    def discard(self, role: str | None) -> None:
        if role is not None:
            self._roles.discard(role)


class UserMetadata(Identity):
    """Contains user metadata such as the password or hash.

    Args:
        config: The configuration object.
        authcid: The authentication identity for the user.
        password: The password string or hash digest.
        params: The user metadata parameters.

    """

    _empty_params: Mapping[str, str] = {}

    def __init__(self, config: IMAPConfig, authcid: str, *,
                 password: str | None = None,
                 params: Mapping[str, str] | None = None) -> None:
        super().__init__()
        self.config: Final = config
        self._authcid = authcid
        self._password = password
        self._params = params or {}

    @classmethod
    async def create(cls, config: IMAPConfig, authcid: str, *,
                     password: str | None = None,
                     params: Mapping[str, str] | None = None) -> UserMetadata:
        """Create a new :class:`UserMetadata` by hashing the given *password*
        using the configured hash algorithm. Uses the
        :attr:`~pymap.config.cpu_subsystem` to avoid blocking the main thread.

        Args:
            config: The configuration object.
            authcid: The authentication identity for the user.
            password: The password string or hash digest.
            params: The user metadata parameters.

        """
        if password is not None:
            fut = cls._hash(config, password)
            password = await config.cpu_subsystem.execute(fut)
        return cls(config, authcid, password=password, params=params)

    @classmethod
    async def _hash(cls, config: IMAPConfig, password: str) -> str:
        prepped = config.password_prep(password)
        return config.hash_context.hash(prepped)

    @property
    def authcid(self) -> str:
        return self._authcid

    def compare_secret(self, value: str) -> bool:
        password = self.password
        if password is not None:
            hash_context = self.config.hash_context.copy()
            return hash_context.verify(value, password)
        return False

    def get_clear_secret(self) -> str | None:
        if isinstance(self.config.hash_context, Cleartext):
            return self.password
        return None

    @property
    def password(self) -> str | None:
        """The password string or hash digest."""
        return self._password

    @property
    def roles(self) -> UserRoles:
        """A set of role strings given to the user. These strings only have
        meaning to the backend.

        """
        return UserRoles()

    @property
    def params(self) -> Mapping[str, str]:
        """Additional parameters associated with the user metadata."""
        return self._params

    def get_key(self, identifier: str) -> bytes | None:
        """Find the token key for the given identifier associated with this
        user.

        Args:
            identifier: Any string that can facilitate the lookup of the key.

        """
        return None

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
        cpu_subsystem = self.config.cpu_subsystem
        fut = self._check_secret(creds)
        if not await cpu_subsystem.execute(fut):
            raise InvalidAuth()

    async def _check_secret(self, creds: ServerCredentials) -> bool:
        return creds.verify(self)
