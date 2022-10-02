
from __future__ import annotations

import re
from collections.abc import Set
from datetime import datetime, timezone
from typing import Final

from pymacaroons import Macaroon, Verifier
from pymacaroons.exceptions import MacaroonDeserializationException, \
    MacaroonInvalidSignatureException
from pysasl.identity import Identity
from pysasl.prep import Preparation

from . import TokensBase
from ..interfaces.token import TokenCredentials
from ..user import UserMetadata

__all__ = ['MacaroonTokens', 'MacaroonCredentials']


class MacaroonTokens(TokensBase):
    """Creates and parses :class:`~pymacaroons.Macaroon` tokens."""

    @property
    def _prepare(self) -> Preparation:
        return self.config.password_prep

    def get_login_token(self, identifier: str, authcid: str, key: bytes, *,
                        authzid: str | None = None,
                        location: str | None = None,
                        expiration: datetime | None = None) -> str:
        macaroon = Macaroon(location=location, identifier=identifier, key=key)
        macaroon.add_first_party_caveat(f'authcid = {self._prepare(authcid)}')
        if authzid is not None:
            macaroon.add_first_party_caveat(f'authzid = {authzid}')
        if expiration is not None:
            macaroon.add_first_party_caveat(f'time < {expiration.isoformat()}')
        serialized: str = macaroon.serialize()
        return serialized

    def get_admin_token(self, admin_key: bytes | None, *,
                        authzid: str | None = None,
                        location: str | None = None,
                        expiration: datetime | None = None) \
            -> str | None:
        if admin_key is None:
            return None
        macaroon = Macaroon(location=location, identifier='', key=admin_key)
        macaroon.add_first_party_caveat('role = admin')
        if authzid is not None:
            macaroon.add_first_party_caveat(f'authzid = {authzid}')
        if expiration is not None:
            macaroon.add_first_party_caveat(f'time < {expiration.isoformat()}')
        serialized: str = macaroon.serialize()
        return serialized

    def parse(self, authzid: str, token: str, *,
              admin_keys: Set[bytes] = frozenset()) -> MacaroonCredentials:
        try:
            return MacaroonCredentials(authzid, token, admin_keys,
                                       self._prepare)
        except MacaroonDeserializationException as exc:
            raise ValueError('invalid macaroon') from exc


class MacaroonCredentials(TokenCredentials):
    """Authenticate using a `Macaroon`_ token. Tokens may be created with
    either :meth:`~MacaroonTokens.get_login_token` or
    :meth:`~MacaroonTokens.get_admin_token`.

    Either type of token may use a caveat with ``time <`` and a
    :func:`~datetime.datetime.fromisoformat` string to limit how long the token
    is valid.

    .. _Macaroon: https://github.com/ecordell/pymacaroons#readme

    Args:
        identity: The identity to be authorized.
        serialized: The serialized macaroon string.
        admin_keys: The admin token string.
        prepare: The preparation algorithm function.

    """

    _caveat = re.compile(r'^(\w+) ([^\w\s]+) (.*)$', re.ASCII)

    def __init__(self, identity: str, serialized: str,
                 admin_keys: Set[bytes], prepare: Preparation) -> None:
        super().__init__()
        self.macaroon: Final = Macaroon.deserialize(serialized)
        self.admin_keys: Final = admin_keys
        self.identity: Final = identity
        self.prepare: Final = prepare

    @property
    def identifier(self) -> str:
        identifier: str = self.macaroon.identifier
        return identifier

    @property
    def role(self) -> str | None:
        for caveat in self.macaroon.first_party_caveats():
            caveat_id = caveat.caveat_id
            if caveat_id == 'role = admin':
                return 'admin'
        return None

    @property
    def authcid(self) -> str:
        return ''

    @property
    def authzid(self) -> str:
        return self.identity

    def _satisfy(self, predicate: str) -> bool:
        match = self._caveat.match(predicate)
        if match is None:
            return False
        key, op, value = match.groups()
        if key == 'time' and op == '<':
            try:
                end = datetime.fromisoformat(value)
            except ValueError:
                return False
            now = datetime.now(tz=timezone.utc)
            return now < end
        elif key == 'authzid' and op == '=':
            return value == self.authzid
        else:
            return False

    def _verify(self, verifier: Verifier, key: bytes) -> bool:
        try:
            verified: bool = verifier.verify(self.macaroon, key)
        except MacaroonInvalidSignatureException:
            return False
        else:
            return verified

    def _get_login_verifier(self, identity: Identity) -> Verifier:
        verifier = Verifier()
        verifier.satisfy_exact(f'authcid = {self.prepare(identity.authcid)}')
        verifier.satisfy_general(self._satisfy)
        return verifier

    def _get_admin_verifier(self) -> Verifier:
        verifier = Verifier()
        verifier.satisfy_exact('role = admin')
        verifier.satisfy_general(self._satisfy)
        return verifier

    def verify(self, identity: Identity | None) -> bool:
        if self.role == 'admin':
            for admin_key in self.admin_keys:
                verifier = self._get_admin_verifier()
                if self._verify(verifier, admin_key):
                    return True
        if isinstance(identity, UserMetadata):
            key = identity.get_key(self.identifier)
            if key is not None:
                verifier = self._get_login_verifier(identity)
                if self._verify(verifier, key):
                    return True
        return False
