
from __future__ import annotations

from collections.abc import Set
from datetime import datetime
from typing import Optional

from pysasl.creds import AuthenticationCredentials

from ..interfaces.token import TokensInterface
from ..plugin import Plugin

__all__ = ['tokens', 'AllTokens']

#: Registers token plugins.
tokens: Plugin[type[TokensInterface]] = Plugin(
    'pymap.token', default='macaroon')


class AllTokens(TokensInterface):
    """Uses :data:`tokens` to support all registered token types.

    For token creation, the :attr:`~pymap.plugin.Plugin.default` token plugin
    is used. For token parsing, each token plugin is tried until one succeeds.

    """

    def get_login_token(self, identifier: str, key: bytes, *,
                        authzid: str = None, location: str = None,
                        expiration: datetime = None) -> Optional[str]:
        try:
            token_type = tokens.default
        except KeyError:
            return None
        return token_type().get_login_token(
            identifier, key, authzid=authzid, location=location,
            expiration=expiration)

    def get_admin_token(self, admin_key: Optional[bytes], *,
                        authzid: str = None, location: str = None,
                        expiration: datetime = None) -> Optional[str]:
        try:
            token_type = tokens.default
        except KeyError:
            return None
        return token_type().get_admin_token(
            admin_key, authzid=authzid, location=location,
            expiration=expiration)

    def parse(self, authzid: str, token: str, *,
              admin_keys: Set[bytes] = frozenset()) \
            -> AuthenticationCredentials:
        for _, token_type in tokens.registered.items():
            try:
                return token_type().parse(authzid, token,
                                          admin_keys=admin_keys)
            except ValueError:
                pass
        raise ValueError('invalid token')
