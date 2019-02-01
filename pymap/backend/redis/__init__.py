
import hashlib
import json
from argparse import Namespace, ArgumentDefaultsHelpFormatter
from typing import Any, Optional, Tuple, Mapping

from aioredis import create_redis, Redis  # type: ignore
from pysasl import AuthenticationCredentials

from pymap.config import IMAPConfig
from pymap.exceptions import InvalidAuth, MailboxConflict
from pymap.interfaces.backend import BackendInterface
from pymap.interfaces.session import LoginProtocol

from .filter import FilterSet
from .mailbox import Message, MailboxSet
from ..session import BaseSession

try:
    from passlib.apps import ldap_context  # type: ignore
except ImportError:
    ldap_context = None

__all__ = ['RedisBackend', 'Config', 'Session']


class RedisBackend(BackendInterface):
    """Defines a backend that uses redis data structures for mailbox storage.

    """

    def __init__(self, login: LoginProtocol, config: IMAPConfig) -> None:
        super().__init__()
        self._login = login
        self._config = config

    @property
    def login(self) -> LoginProtocol:
        return self._login

    @property
    def config(self) -> IMAPConfig:
        return self._config

    @classmethod
    def add_subparser(cls, subparsers) -> None:
        parser = subparsers.add_parser(
            'redis', help='redis backend',
            formatter_class=ArgumentDefaultsHelpFormatter)
        parser.add_argument('address', nargs='?', default='redis://localhost',
                            help='the redis server address')
        parser.add_argument('--prefix', metavar='VAL', default='',
                            help='the prefix for redis keys')
        parser.add_argument('--users-hash', metavar='KEY',
                            help='the hash key for user lookup')
        parser.add_argument('--users-key', metavar='FORMAT', default='{name}',
                            help='the user lookup key template')
        parser.add_argument('--users-json', action='store_true',
                            help='the user lookup value contains JSON')

    @classmethod
    async def init(cls, args: Namespace) -> 'RedisBackend':
        return cls(Session.login, Config.from_args(args))


class Config(IMAPConfig):
    """The config implementation for the redis backend.

    Args:
        args: The command-line arguments.
        address: The redis server address.
        prefix: The prefix for redis keys.
        users_hash: The hash key for user lookup.
        users_key: The user lookup key template.
        users_json: True if the user lookup value contains JSON.

    """

    def __init__(self, args: Namespace, *, address: str, prefix: str,
                 users_hash: Optional[str], users_key: str,
                 users_json: bool, **extra: Any) -> None:
        super().__init__(args, **extra)
        self._address = address
        self._prefix = prefix
        self._users_hash = users_hash
        self._users_key = users_key
        self._users_json = users_json

    @property
    def address(self) -> str:
        """The redis server address. Defaults to a connection to localhost.

        See Also:
            :func:`aioredis.create_connection`

        """
        return self._address

    @property
    def prefix(self) -> str:
        """The prefix for redis keys. This prefix does not apply to user
        lookup, e.g. :attr:`.users_hash` or :attr:`.users_key`.

        """
        return self._prefix

    @property
    def users_hash(self) -> Optional[str]:
        """The name of the hash where keys are looked up for user login. If
        this value is None, which is the default, keys are looked up in the
        full redis database.

        """
        return self._users_hash

    @property
    def users_key(self) -> str:
        """The key template for looking up user login. The login name
        (:attr:`~pysasl.AuthenticationCredentials.authcid`) is substituted in
        the template in place of ``{name}`` using :meth:`str.format`. By
        default, the template is ``{name}`` so the key will be the unaltered
        login name.

        """
        return self._users_key

    @property
    def users_json(self) -> bool:
        """True if the value from the user lookup key contains a JSON object
        with a ``"password"`` attribute, instead of simply containing the
        password value encoded with UTF-8.

        """
        return self._users_json

    @property
    def prefix_override_hash(self) -> str:
        """The name of a hash used to override user prefixes -- not needed for
        normal operation.

        Typically, the keys used for user data after login are prefixed with
        :attr:`.prefix` and the SHA-1 hash of the login name.  However, if a
        login name is changed, it can still use to its old data by setting
        :attr:`.users_key` in this hash to the prefix before the name change.

        """
        return f'{self.prefix}_prefix'

    @classmethod
    def parse_args(cls, args: Namespace) -> Mapping[str, Any]:
        return {'address': args.address,
                'prefix': args.prefix,
                'users_hash': args.users_hash,
                'users_key': args.users_key,
                'users_json': args.users_json}


class Session(BaseSession[Message]):
    """The session implementation for the redis backend."""

    resource = __name__

    def __init__(self, owner: str, config: Config, mailbox_set: MailboxSet,
                 filter_set: FilterSet) -> None:
        super().__init__(owner)
        self._config = config
        self._mailbox_set = mailbox_set
        self._filter_set = filter_set

    @property
    def config(self) -> IMAPConfig:
        return self._config

    @property
    def mailbox_set(self) -> MailboxSet:
        return self._mailbox_set

    @property
    def filter_set(self) -> FilterSet:
        return self._filter_set

    @classmethod
    async def login(cls, credentials: AuthenticationCredentials,
                    config: Config) -> 'Session':
        """Checks the given credentials for a valid login and returns a new
        session.

        """
        redis = await create_redis(config.address)
        prefix = await cls._check_user(redis, config, credentials)
        mailbox_set = MailboxSet(redis, prefix)
        try:
            await mailbox_set.add_mailbox('INBOX')
        except MailboxConflict:
            pass
        filter_set = FilterSet(redis, prefix)
        return cls(credentials.identity, config, mailbox_set, filter_set)

    @classmethod
    async def _check_user(cls, redis: Redis, config: Config,
                          credentials: AuthenticationCredentials) -> bytes:
        user = credentials.authcid
        password, prefix = await cls._get_password(redis, config, user)
        if user != credentials.identity:
            raise InvalidAuth()
        elif ldap_context is None or not credentials.has_secret:
            if not credentials.check_secret(password):
                raise InvalidAuth()
        elif not ldap_context.verify(credentials.secret, password):
            raise InvalidAuth()
        return prefix

    @classmethod
    async def _get_password(cls, redis: Redis, config: Config,
                            name: str) -> Tuple[str, bytes]:
        key = config.users_key.format(name=name)
        multi = redis.multi_exec()
        if config.users_hash is None:
            multi.get(key)
        else:
            multi.hget(config.users_hash, key)
        multi.hget(config.prefix_override_hash, key)
        value, prefix = await multi.execute()
        if prefix is None:
            prefix = cls._get_prefix(name, config.prefix)
        if value is None:
            raise InvalidAuth()
        elif config.users_json:
            value_obj = json.loads(value)
            try:
                return value_obj['password'], prefix
            except KeyError as exc:
                raise InvalidAuth() from exc
        else:
            return value.decode('utf-8'), prefix

    @classmethod
    def _get_prefix(cls, name: str, root_prefix: str) -> bytes:
        name_bytes = name.encode('utf-8')
        hash_obj = hashlib.sha1()
        hash_obj.update(name_bytes)
        prefix = root_prefix + hash_obj.hexdigest()
        return prefix.encode('utf-8')
