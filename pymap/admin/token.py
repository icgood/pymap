
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Optional
from typing_extensions import Final

from pymacaroons import Macaroon, Verifier
from pymacaroons.exceptions import MacaroonDeserializationException, \
    MacaroonInvalidSignatureException
from pysasl.creds import StoredSecret, AuthenticationCredentials

__all__ = ['get_login_token', 'get_admin_token', 'TokenCredentials']


def get_login_token(identifier: str, key: bytes, *, location: str = None,
                    expiration: datetime = None,
                    authzid: str = None) -> Macaroon:
    """Produce a token :class:`~pymacaroons.Macaroon` to authenticate as a
    specific user.

    Args:
        identifier: Used to identify and lookup the *key* value.
        key: The key used to create and verify the token for the user.
        location: Optional hint describing where the token is valid.
        expiration: When the token should expire.
        authzid: If given, limits the token to the given authorization ID.

    """
    macaroon = Macaroon(location=location, identifier=identifier, key=key)
    macaroon.add_first_party_caveat('type = login')
    if authzid is not None:
        macaroon.add_first_party_caveat(f'authzid = {authzid}')
    if expiration is not None:
        macaroon.add_first_party_caveat(f'time < {expiration.isoformat()}')
    return macaroon


def get_admin_token(admin_token: bytes, expiration: Optional[datetime], *,
                    location: str = None, authzid: str = None) -> Macaroon:
    """Produce a token :class:`~pymacaroons.Macaroon` to authenticate as an
    admin that may perform operations on users.

    Args:
        admin_token: The admin token string.
        expiration: When the token should expire.
        location: Optional hint describing where the token is valid.
        authzid: If given, limits the token to the given authorization ID.

    """
    macaroon = Macaroon(location=location, identifier='', key=admin_token)
    macaroon.add_first_party_caveat('type = admin')
    if authzid is not None:
        macaroon.add_first_party_caveat(f'authzid = {authzid}')
    if expiration is not None:
        macaroon.add_first_party_caveat(f'time < {expiration.isoformat()}')
    return macaroon


class TokenCredentials(AuthenticationCredentials):
    """Authenticate using a `Macaroon`_ token. Tokens may be created with
    either :func:`get_login_token` or :func:`get_admin_token`.

    Either type of token may use a caveat with ``time < `` and a
    :func:`~datetime.datetime.fromisoformat` string to limit how long the token
    is valid.

    .. Macaroon: https://github.com/ecordell/pymacaroons#readme

    Args:
        serialized: The serialized macaroon string.
        admin_token: The admin token string.
        identity: The identity to be authorized.

    """

    _caveat = re.compile(r'^(\w+) ([^\w\s]+) (.*)$', re.ASCII)

    def __init__(self, serialized: str, admin_token: Optional[bytes],
                 identity: str) -> None:
        try:
            macaroon = Macaroon.deserialize(serialized)
        except MacaroonDeserializationException as exc:
            raise ValueError('invalid token') from exc
        super().__init__(macaroon.identifier, '', identity)
        self.macaroon: Final = macaroon
        self.admin_token: Final = admin_token
        self._type = self._find_type(macaroon)

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
    def authcid_type(self) -> Optional[str]:
        return self._type

    @property
    def has_secret(self) -> bool:
        return False

    @property
    def secret(self) -> str:
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
                     key: bytes = None, **other: Optional[str]) -> bool:
        if key is not None:
            verifier = self._get_login_verifier()
            if self._verify(verifier, key):
                return True
        admin_token = self.admin_token
        if admin_token is not None:
            verifier = self._get_admin_verifier()
            if self._verify(verifier, admin_token):
                return True
        return False
