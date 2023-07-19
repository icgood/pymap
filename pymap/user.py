
from __future__ import annotations

import secrets
from dataclasses import dataclass
from random import getrandbits
from typing import overload, Final

from pysasl.creds.server import ServerCredentials
from pysasl.hashing import Cleartext
from pysasl.identity import Identity

from .config import IMAPConfig
from .frozen import frozendict
from .versioned import Versioned

__all__ = ['Passwords', 'UserMetadata']

_empty_roles: frozenset[str] = frozenset()
_empty_params: frozendict[str, str] = frozendict()


class Passwords:
    """Helper utility for performing password operations in a CPU bound pool.

    Args:
        config: The IMAP config object.

    """

    __slots__ = ['password_prep', 'cpu_subsystem', 'hash_context']

    def __init__(self, config: IMAPConfig) -> None:
        super().__init__()
        self.password_prep: Final = config.password_prep
        self.cpu_subsystem: Final = config.cpu_subsystem
        self.hash_context: Final = config.hash_context

    @overload
    async def hash_password(self, password: str) -> str:
        ...

    @overload
    async def hash_password(self, password: None) -> None:
        ...

    async def hash_password(self, password: str | None) -> str | None:
        """Hash the given *password* using the configured hash algorithm.

        Args:
            password: The password string to hash.

        """
        if password is not None:
            fut = self._hash_password(password)
            return await self.cpu_subsystem.execute(fut)
        return None

    async def _hash_password(self, password: str) -> str:
        prepped = self.password_prep(password)
        return self.hash_context.hash(prepped)

    async def check_password(self, identity: Identity,
                             credentials: ServerCredentials) -> bool:
        """Check the *credentials* against the SASL *identity*.

        Args:
            identity: The identity to check against.
            credentials: The credentials to check with.

        """
        fut = self._check_password(identity, credentials)
        return await self.cpu_subsystem.execute(fut)

    async def _check_password(self, identity: Identity,
                              credentials: ServerCredentials) -> bool:
        return credentials.verify(identity)


@dataclass(frozen=True)
class UserMetadata(Identity, Versioned[int | None]):
    """Defines the attributes associated with a user identity."""

    #: The config object.
    config: IMAPConfig

    #: The user identity name.
    name: str

    #: The entity tag of the current version of this metadata.
    entity_tag: int | None = None

    #: The entity tag of the previous version of this metadata.
    previous_entity_tag: int | None = None

    #: The password string or hash digest.
    password: str | None = None

    #: The private key used to verify tokens.
    token_key: bytes | None = None

    #: The set of roles assigned to the user.
    roles: frozenset[str] = _empty_roles

    #: Additional parameters associated with the user.
    params: frozendict[str, str] = _empty_params

    @property
    def authcid(self) -> str:
        return self.name

    def compare_authcid(self, authcid: str) -> bool:
        prepare = self.config.password_prep
        self_authcid = prepare(self.authcid).encode('utf-8')
        other_authcid = prepare(authcid).encode('utf-8')
        return secrets.compare_digest(self_authcid, other_authcid)

    def compare_secret(self, value: str) -> bool:
        prepare = self.config.password_prep
        password = self.password
        if password is not None:
            hash_context = self.config.hash_context.copy()
            return hash_context.verify(prepare(value), prepare(password))
        return False

    def get_clear_secret(self) -> str | None:
        if isinstance(self.config.hash_context, Cleartext):
            return self.password
        return None

    @classmethod
    def new_entity_tag(cls) -> int:
        return getrandbits(64)
