
from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping, MutableSet
from typing import Final

from pysasl.creds.server import ServerCredentials
from pysasl.hashing import Cleartext

from .config import IMAPConfig
from .exceptions import InvalidAuth
from .interfaces.login import UserInterface

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


class UserMetadata(UserInterface):
    """Contains user metadata such as the password or hash.

    Args:
        config: The configuration object.
        authcid: The authentication identity for the user.
        password: The password string or hash digest.
        params: Metadata parameters associated with the user.

    """

    def __init__(self, config: IMAPConfig, authcid: str, *,
                 password: str | None = None,
                 **params: str | None) -> None:
        super().__init__()
        self.config: Final = config
        self._authcid = authcid
        self._password = password
        self._params = {key: val for key, val in params.items()
                        if val is not None}

    @property
    def authcid(self) -> str:
        return self._authcid

    @property
    def password(self) -> str | None:
        return self._password

    @property
    def params(self) -> Mapping[str, str]:
        return self._params

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
    def roles(self) -> UserRoles:
        return UserRoles([self.params.get('role')])

    def get_key(self, identifier: str) -> bytes | None:
        if identifier == self.authcid and 'key' in self.params:
            return bytes.fromhex(self.params['key'])
        return None

    async def check_password(self, creds: ServerCredentials) -> None:
        cpu_subsystem = self.config.cpu_subsystem
        fut = self._check_secret(creds)
        if not await cpu_subsystem.execute(fut):
            raise InvalidAuth()

    async def _check_secret(self, creds: ServerCredentials) -> bool:
        return creds.verify(self)
