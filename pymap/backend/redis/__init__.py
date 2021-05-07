
from __future__ import annotations

import json
import uuid
from argparse import ArgumentParser, Namespace
from collections.abc import Awaitable, Callable, Mapping, AsyncIterator
from contextlib import closing, asynccontextmanager, AsyncExitStack
from datetime import datetime
from functools import partial
from secrets import token_bytes
from typing import Any, Optional, Final

from aioredis import create_redis, Redis, ConnectionClosedError
from pysasl.creds import AuthenticationCredentials

from pymap.bytes import BytesFormat
from pymap.config import BackendCapability, IMAPConfig
from pymap.context import connection_exit
from pymap.exceptions import AuthorizationFailure, IncompatibleData, \
    NotAllowedError, UserNotFound
from pymap.health import HealthStatus
from pymap.interfaces.backend import BackendInterface
from pymap.interfaces.login import LoginInterface, IdentityInterface
from pymap.interfaces.token import TokensInterface
from pymap.token import AllTokens
from pymap.user import UserMetadata

from .cleanup import CleanupTask
from .filter import FilterSet
from .keys import DATA_VERSION, RedisKey, GlobalKeys, CleanupKeys, \
    NamespaceKeys
from .mailbox import Message, MailboxSet
from ..session import BaseSession

__all__ = ['RedisBackend', 'Config', 'Session']


class RedisBackend(BackendInterface):
    """Defines a backend that uses redis data structures for mailbox storage.

    """

    def __init__(self, login: Login, config: Config,
                 status: HealthStatus) -> None:
        super().__init__()
        self._login = login
        self._config = config
        self._status = status

    @property
    def login(self) -> Login:
        return self._login

    @property
    def config(self) -> Config:
        return self._config

    @property
    def status(self) -> HealthStatus:
        return self._status

    @classmethod
    def add_subparser(cls, name: str, subparsers: Any) -> ArgumentParser:
        parser = subparsers.add_parser(name, help='redis backend')
        parser.add_argument('--address', metavar='URL',
                            default='redis://localhost',
                            help='the redis server address')
        parser.add_argument('--select', metavar='DB', type=int,
                            help='the redis database for mail data')
        parser.add_argument('--separator', metavar='CHAR', default='/',
                            help='the redis key segment separator')
        parser.add_argument('--prefix', metavar='VAL', default='/mail',
                            help='the mail data key prefix')
        parser.add_argument('--users-prefix', metavar='VAL', default='/users',
                            help='the user lookup key prefix')
        parser.add_argument('--users-json', action='store_true',
                            help='the user lookup value contains JSON')
        return parser

    @classmethod
    async def init(cls, args: Namespace, **overrides: Any) \
            -> tuple[RedisBackend, Config]:
        config = Config.from_args(args)
        status = HealthStatus()
        connect_redis = partial(cls._connect_redis, config, status)
        login = Login(config, connect_redis)
        return cls(login, config, status), config

    @classmethod
    async def _connect_redis(cls, config: Config,
                             status: HealthStatus) -> Redis:
        try:
            redis = await create_redis(config.address)
        except (ConnectionClosedError, OSError):
            status.set_unhealthy()
            raise
        else:
            status.set_healthy()
            stack = connection_exit.get()
            stack.enter_context(closing(redis))
            return redis

    async def start(self, stack: AsyncExitStack) -> None:
        config = self._config
        global_keys = config._global_keys
        connect_redis = partial(self._connect_redis, config, self._status)
        cleanup_task = CleanupTask(connect_redis, global_keys).start()
        stack.callback(cleanup_task.cancel)


class Config(IMAPConfig):
    """The config implementation for the redis backend.

    Args:
        args: The command-line arguments.
        address: The redis server address.
        select: The redis database for mail data.
        separator: The redis key segment separator.
        prefix: The prefix for mail data keys.
        users_prefix: The user lookup key prefix.
        users_json: True if the user lookup value contains JSON.

    """

    def __init__(self, args: Namespace, *, address: str, select: Optional[int],
                 separator: bytes, prefix: bytes, users_prefix: bytes,
                 users_json: bool, **extra: Any) -> None:
        super().__init__(args, admin_key=token_bytes(), **extra)
        self._address = address
        self._select = select
        self._separator = separator
        self._prefix = prefix
        self._users_prefix = users_prefix
        self._users_json = users_json

    @property
    def backend_capability(self) -> BackendCapability:
        return BackendCapability(idle=True, object_id=True, multi_append=True)

    @property
    def address(self) -> str:
        """The redis server address. Defaults to a connection to localhost.

        See Also:
            :func:`aioredis.create_connection`

        """
        return self._address

    @property
    def select(self) -> Optional[int]:
        """The redis database for mail data. If given, the `SELECT`_ command is
        called after successful user lookup.

        .. _SELECT: https://redis.io/commands/select

        """
        return self._select

    @property
    def separator(self) -> bytes:
        """The bytestring used to separate segments of composite redis keys."""
        return self._separator

    @property
    def prefix(self) -> bytes:
        """The prefix for mail data keys. This prefix does not apply to
        :attr:`.users_key`.

        """
        return self._prefix

    @property
    def users_prefix(self) -> bytes:
        """The prefix for user lookup keys."""
        return self._users_prefix

    @property
    def users_json(self) -> bool:
        """True if the value from the user lookup key contains a JSON object
        with a ``"password"`` attribute, instead of a redis hash with a
        ``password`` key.

        See Also:
            `redis hashes
            <https://redis.io/topics/data-types-intro#redis-hashes>`_

        """
        return self._users_json

    @property
    def _joiner(self) -> BytesFormat:
        return BytesFormat(self.separator)

    @property
    def _users_root(self) -> RedisKey:
        return RedisKey(self._joiner, [self.users_prefix], {})

    @property
    def _global_keys(self) -> GlobalKeys:
        key = RedisKey(self._joiner, [self.prefix], {})
        return GlobalKeys(key)

    @classmethod
    def parse_args(cls, args: Namespace) -> Mapping[str, Any]:
        return {**super().parse_args(args),
                'address': args.address,
                'select': args.select,
                'separator': args.separator.encode('utf-8'),
                'prefix': args.prefix.encode('utf-8'),
                'users_prefix': args.users_prefix.encode('utf-8'),
                'users_json': args.users_json}


class Session(BaseSession[Message]):
    """The session implementation for the redis backend."""

    resource = __name__

    def __init__(self, redis: Redis, owner: str, config: Config,
                 mailbox_set: MailboxSet, filter_set: FilterSet) -> None:
        super().__init__(owner)
        self._redis = redis
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


class Login(LoginInterface):
    """The login implementation for the redis backend."""

    def __init__(self, config: Config,
                 connect_redis: Callable[[], Awaitable[Redis]]) -> None:
        super().__init__()
        self._config = config
        self._connect_redis = connect_redis
        self._tokens = AllTokens()

    @property
    def tokens(self) -> TokensInterface:
        return self._tokens

    async def authenticate(self, credentials: AuthenticationCredentials) \
            -> Identity:
        config = self._config
        redis = await self._connect_redis()
        authcid = credentials.authcid
        token_key: Optional[bytes] = None
        role: Optional[str] = None
        if credentials.authcid_type == 'admin-token':
            authcid = credentials.identity
            role = 'admin'
        try:
            authcid_identity = Identity(config, self.tokens, redis, authcid)
            metadata = await authcid_identity.get()
        except UserNotFound:
            metadata = UserMetadata(config)
        if 'key' in metadata.params:
            token_key = bytes.fromhex(metadata.params['key'])
        role = role or metadata.role
        await metadata.check_password(credentials, token_key=token_key)
        if role != 'admin' and authcid != credentials.identity:
            raise AuthorizationFailure()
        return Identity(config, self.tokens, redis, credentials.identity, role)


class Identity(IdentityInterface):
    """The identity implementation for the redis backend."""

    def __init__(self, config: Config, tokens: TokensInterface,
                 redis: Redis, name: str, role: str = None) -> None:
        super().__init__()
        self.config: Final = config
        self.tokens: Final = tokens
        self._redis: Optional[Redis] = redis
        self._name = name
        self._role = role

    @property
    def name(self) -> str:
        return self._name

    @property
    def redis(self) -> Redis:
        redis = self._redis
        if redis is None:
            # Other methods may not be called after new_session(), since it
            # may have called SELECT on the connection.
            raise RuntimeError()
        return redis

    async def new_token(self, *, expiration: datetime = None) -> Optional[str]:
        metadata = await self.get()
        if 'key' not in metadata.params:
            return None
        key = bytes.fromhex(metadata.params['key'])
        return self.tokens.get_login_token(self.name, key)

    @asynccontextmanager
    async def new_session(self) -> AsyncIterator[Session]:
        config = self.config
        redis = self.redis
        self._redis = None
        if config.select is not None:
            await redis.select(config.select)
        global_keys = config._global_keys
        namespace = await self._get_namespace(redis, global_keys, self.name)
        ns_keys = NamespaceKeys(global_keys, namespace)
        cl_keys = CleanupKeys(global_keys)
        mailbox_set = MailboxSet(redis, ns_keys, cl_keys)
        filter_set = FilterSet(redis, ns_keys)
        try:
            await mailbox_set.add_mailbox('INBOX')
        except ValueError:
            pass
        yield Session(redis, self.name, config, mailbox_set, filter_set)

    async def _get_namespace(self, redis: Redis, global_keys: GlobalKeys,
                             user: str) -> bytes:
        user_key = user.encode('utf-8')
        new_namespace = uuid.uuid4().hex.encode('ascii')
        ns_val = b'%d/%b' % (DATA_VERSION, new_namespace)
        multi = redis.multi_exec()
        multi.hsetnx(global_keys.namespaces, user_key, ns_val)
        multi.hget(global_keys.namespaces, user_key)
        _, ns_val = await multi.execute()
        version, namespace = ns_val.split(b'/', 1)
        if int(version) != DATA_VERSION:
            raise IncompatibleData()
        return namespace

    async def get(self) -> UserMetadata:
        redis = self.redis
        user_bytes = self.name.encode('utf-8')
        user_key = self.config._users_root.end(user_bytes)
        if self.config.users_json:
            json_data = await redis.get(user_key)
            if json_data is None:
                raise UserNotFound(self.name)
            data_dict = json.loads(json_data)
        else:
            data_dict = await redis.hgetall(user_key, encoding='utf-8')
            if data_dict is None:
                raise UserNotFound(self.name)
        return UserMetadata(self.config, **data_dict)

    async def set(self, metadata: UserMetadata) -> None:
        config = self.config
        redis = self.redis
        if self._role != 'admin' and metadata.role:
            raise NotAllowedError('Cannot assign role.')
        user_key = config._users_root.end(self.name.encode('utf-8'))
        user_dict = metadata.to_dict(key=token_bytes().hex())
        if self.config.users_json:
            json_data = json.dumps(user_dict)
            await redis.set(user_key, json_data)
        else:
            multi = redis.multi_exec()
            multi.delete(user_key)
            multi.hmset_dict(user_key, user_dict)
            await multi.execute()

    async def delete(self) -> None:
        config = self.config
        user_key = config._users_root.end(self.name.encode('utf-8'))
        if not await self.redis.delete(user_key):
            raise UserNotFound(self.name)
