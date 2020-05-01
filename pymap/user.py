
from __future__ import annotations

from typing import Any, Optional, Mapping, Dict
from typing_extensions import Final

from pysasl import AuthenticationCredentials

from .config import IMAPConfig
from .exceptions import InvalidAuth

__all__ = ['UserMetadata']


class UserMetadata:
    """Contains user metadata including the password or hash.

    Args:
        config: The configuration object.
        password: The password string or hash digest.
        params: Additional metadata parameters associated with the user.

    """

    def __init__(self, config: IMAPConfig, password: Optional[str], *,
                 params: Mapping[str, str] = None) -> None:
        super().__init__()
        self.config: Final = config
        self.password: Final = password
        self.params: Final = params or {}

    @classmethod
    def from_dict(cls, config: IMAPConfig, data: Mapping[str, Any]) \
            -> UserMetadata:
        """Build a new :class:`UserMetadata` from a dictionary containing
        the password information. Fields must either be :func:`str` or
        :func:`int`, bytestrings should be hex-encoded.

        See Also:
            :meth:`.to_dict`

        Args:
            config: The configuration object.
            data: The password data dictionary.

        """
        params = dict(data)
        password = params.pop('password', None)
        return cls(config, password, params=params)

    def to_dict(self) -> Mapping[str, Any]:
        """Returns the password comparison data in a JSON-serializable
        dictionary for persistence and transfer.

        See Also:
            :meth:`.from_dict`

        """
        data: Dict[str, Any] = dict(self.params)
        if self.password:
            data['password'] = self.password
        return data

    def check_password(self, creds: AuthenticationCredentials) -> None:
        """Check the given credentials against the known password comparison
        data. If the known data used a hash, then the equivalent hash of the
        provided secret is compared.

        Args:
            creds: The provided authentication credentials.

        Raises:
            :class:`~pymap.exceptions.InvalidAuth`

        """
        config = self.config
        if self.password is None:
            raise InvalidAuth()
        elif not creds.check_secret(self.password, hash=config.hash_context):
            raise InvalidAuth()
