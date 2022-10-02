
from __future__ import annotations

from collections.abc import Sequence, Set
from datetime import datetime
from functools import cached_property
from typing import Final

from ..config import IMAPConfig
from ..interfaces.token import TokenCredentials, TokensInterface
from ..plugin import Plugin

__all__ = ['tokens', 'TokensBase', 'AllTokens']

#: Registers token plugins.
tokens: Plugin[TokensBase] = Plugin('pymap.token', default='macaroon')


class TokensBase(TokensInterface):
    """Base class for token types registered by :data:`tokens`.

    Args:
        config: The IMAP configuration object.

    """

    def __init__(self, config: IMAPConfig) -> None:
        super().__init__()
        self.config: Final = config


class AllTokens(TokensBase):
    """Uses :data:`tokens` to support all registered token types.

    For token creation, the :attr:`~pymap.plugin.Plugin.default` token plugin
    is used. For token parsing, each token plugin is tried until one succeeds.

    """

    @cached_property
    def _default_tokens(self) -> TokensInterface | None:
        try:
            token_type = tokens.default
        except KeyError:
            return None
        else:
            return token_type(self.config)

    @cached_property
    def _tokens(self) -> Sequence[TokensInterface]:
        all_tokens = []
        config = self.config
        for token_type in tokens.registered.values():
            if token_type == tokens.default:
                assert self._default_tokens is not None
                all_tokens.append(self._default_tokens)
            else:
                all_tokens.append(token_type(config))
        return all_tokens

    def get_login_token(self, identifier: str, authcid: str, key: bytes, *,
                        authzid: str | None = None,
                        location: str | None = None,
                        expiration: datetime | None = None) \
            -> str | None:
        tokens = self._default_tokens
        if tokens is None:
            return None
        return tokens.get_login_token(
            identifier, authcid, key, authzid=authzid, location=location,
            expiration=expiration)

    def get_admin_token(self, admin_key: bytes | None, *,
                        authzid: str | None = None,
                        location: str | None = None,
                        expiration: datetime | None = None) \
            -> str | None:
        tokens = self._default_tokens
        if tokens is None:
            return None
        return tokens.get_admin_token(
            admin_key, authzid=authzid, location=location,
            expiration=expiration)

    def parse(self, authzid: str, token: str, *,
              admin_keys: Set[bytes] = frozenset()) \
            -> TokenCredentials:
        for tokens in self._tokens:
            try:
                return tokens.parse(authzid, token, admin_keys=admin_keys)
            except ValueError:
                pass
        raise ValueError('invalid token')
