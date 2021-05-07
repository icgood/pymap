
from __future__ import annotations

import re
from collections.abc import Set
from datetime import datetime, timezone
from typing import Any, Final, Optional, NoReturn

from pymacaroons import Macaroon, Verifier
from pymacaroons.exceptions import MacaroonDeserializationException, \
    MacaroonInvalidSignatureException
from pysasl.creds import AuthenticationCredentials, StoredSecret

from ..interfaces.token import TokensInterface

__all__ = ['MacaroonTokens', 'MacaroonCredentials']


class MacaroonTokens(TokensInterface):
    """Creates and parses :class:`~pymacaroons.Macaroon` tokens."""

    def get_login_token(self, identifier: str, key: bytes, *,
                        authzid: str = None, location: str = None,
                        expiration: datetime = None) -> str:
        macaroon = Macaroon(location=location, identifier=identifier, key=key)
        macaroon.add_first_party_caveat('type = login')
        if authzid is not None:
            macaroon.add_first_party_caveat(f'authzid = {authzid}')
        if expiration is not None:
            macaroon.add_first_party_caveat(f'time < {expiration.isoformat()}')
        return macaroon.serialize()

    def get_admin_token(self, admin_key: Optional[bytes], *,
                        authzid: str = None, location: str = None,
                        expiration: datetime = None) -> Optional[str]:
        if admin_key is None:
            return None
        macaroon = Macaroon(location=location, identifier='', key=admin_key)
        macaroon.add_first_party_caveat('type = admin')
        if authzid is not None:
            macaroon.add_first_party_caveat(f'authzid = {authzid}')
        if expiration is not None:
            macaroon.add_first_party_caveat(f'time < {expiration.isoformat()}')
        return macaroon.serialize()

    def parse(self, authzid: str, token: str, *,
              admin_keys: Set[bytes] = frozenset()) -> MacaroonCredentials:
        try:
            return MacaroonCredentials(authzid, token, admin_keys)
        except MacaroonDeserializationException as exc:
            raise ValueError('invalid macaroon') from exc


class MacaroonCredentials(AuthenticationCredentials):
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

    """

    _caveat = re.compile(r'^(\w+) ([^\w\s]+) (.*)$', re.ASCII)

    def __init__(self, identity: str, serialized: str,
                 admin_keys: Set[bytes]) -> None:
        macaroon = Macaroon.deserialize(serialized)
        authcid_type = self._find_type(macaroon)
        super().__init__(macaroon.identifier, '', identity,
                         authcid_type=authcid_type)
        self.macaroon: Final = macaroon
        self.admin_keys: Final = admin_keys

    @classmethod
    def _find_type(cls, macaroon: Macaroon) -> Optional[str]:
        for caveat in macaroon.first_party_caveats():
            caveat_id = caveat.caveat_id
            if caveat_id == 'type = admin':
                return 'admin-token'
            elif caveat_id == 'type = login':
                return 'login-token'
        return None

    @property
    def has_secret(self) -> bool:
        return False

    @property
    def secret(self) -> NoReturn:
        raise AttributeError('secret')

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
            return verifier.verify(self.macaroon, key)
        except MacaroonInvalidSignatureException:
            return False

    def _get_login_verifier(self) -> Verifier:
        verifier = Verifier()
        verifier.satisfy_general(self._satisfy)
        verifier.satisfy_exact('type = login')
        return verifier

    def _get_admin_verifier(self) -> Verifier:
        verifier = Verifier()
        verifier.satisfy_general(self._satisfy)
        verifier.satisfy_exact('type = admin')
        return verifier

    def check_secret(self, secret: Optional[StoredSecret], *,
                     key: bytes = None, **other: Any) -> bool:
        if key is not None:
            verifier = self._get_login_verifier()
            if self._verify(verifier, key):
                return True
        for admin_key in self.admin_keys:
            verifier = self._get_admin_verifier()
            if self._verify(verifier, admin_key):
                return True
        return False
