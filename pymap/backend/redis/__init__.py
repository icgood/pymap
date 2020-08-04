
from __future__ import annotations

import asyncio
import json
import uuid
from argparse import ArgumentParser, Namespace
from contextlib import closing, asynccontextmanager
from functools import partial
from typing import Any, Optional, Tuple, Mapping, Sequence, Awaitable, \
    AsyncIterator, AsyncIterable

from aioredis import create_redis, Redis  # type: ignore
from pysasl import AuthenticationCredentials
from pysasl.external import ExternalResult

from pymap.bytes import BytesFormat
from pymap.config import BackendCapability, IMAPConfig
from pymap.context import connection_exit
from pymap.exceptions import InvalidAuth, IncompatibleData, UserNotFound
from pymap.interfaces.backend import BackendInterface, ServiceInterface
from pymap.interfaces.session import LoginProtocol
from pymap.interfaces.users import UsersInterface
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

    def __init__(self, users: Users, config: Config) -> None:
        super().__init__()
        self._users = users
        self._config = config

    @property
    def login(self) -> Users:
        return self._users

    @property
    def users(self) -> Users:
        return self._users

    @property
    def config(self) -> Config:
        return self._config

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
    async def init(cls, args: Namespace) -> Tuple[RedisBackend, Config]:
        config = Config.from_args(args)
        users = Users(config)
        return cls(users, config), config

    async def start(self, services: Sequence[ServiceInterface]) -> Awaitable:
        config = self._config
        global_keys = config._global_keys
        connect_redis = partial(create_redis, config.address)
        cleanup_task = CleanupTask(connect_redis, global_keys)
        tasks = [await cleanup_task.start()]
        for service in services:
            tasks.append(await service.start())
        return asyncio.gather(*tasks)


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
        super().__init__(args, **extra)
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

    def __init__(self, redis: Redis, owner: str, config: Config, users: Users,
                 mailbox_set: MailboxSet, filter_set: FilterSet) -> None:
        super().__init__(owner)
        self._redis = redis
        self._config = config
        self._users = users
        self._mailbox_set = mailbox_set
        self._filter_set = filter_set

    @property
    def config(self) -> IMAPConfig:
        return self._config

    @property
    def users(self) -> Users:
        return self._users

    @property
    def mailbox_set(self) -> MailboxSet:
        return self._mailbox_set

    @property
    def filter_set(self) -> FilterSet:
        return self._filter_set


class Users(LoginProtocol, UsersInterface):
    """The users implementation for the redis backend."""

    def __init__(self, config: Config) -> None:
        super().__init__()
        self.config = config

    @classmethod
    async def _connect_redis(cls, address: str) -> Redis:
        redis = await create_redis(address)
        stack = connection_exit.get()
        stack.enter_context(closing(redis))
        return redis

    async def list_users(self, *, match: str = None) \
            -> AsyncIterable[Sequence[str]]:
        config = self.config
        redis = await self._connect_redis(config.address)
        users_root = config._users_root.end(b'')
        if match is None:
            match_key = users_root + b'*'
        else:
            match_key = users_root + match.encode('utf-8')
        cur = b'0'
        while cur:
            cur, keys = await redis.scan(cur, match=match_key)
            yield [key[len(users_root):] for key in keys
                   if key.startswith(users_root)]

    async def get_user(self, user: str) -> UserMetadata:
        config = self.config
        redis = await self._connect_redis(config.address)
        data = await self._get_user(redis, user)
        if data is None:
            raise UserNotFound()
        return data

    async def set_user(self, user: str, data: UserMetadata) -> None:
        config = self.config
        redis = await self._connect_redis(config.address)
        user_key = config._users_root.end(user.encode('utf-8'))
        data_dict = data.to_dict()
        if self.config.users_json:
            json_data = json.dumps(data_dict)
            await redis.set(user_key, json_data)
        else:
            multi = redis.multi_exec()
            multi.delete(user_key)
            multi.hmset_dict(user_key, data_dict)
            await multi.execute()

    async def delete_user(self, user: str) -> None:
        config = self.config
        redis = await self._connect_redis(config.address)
        user_key = config._users_root.end(user.encode('utf-8'))
        if not await redis.delete(user_key):
            raise UserNotFound()

    @asynccontextmanager
    async def __call__(self, credentials: AuthenticationCredentials) \
            -> AsyncIterator[Session]:
        """Checks the given credentials for a valid login and returns a new
        session.

        """
        config = self.config
        redis = await self._connect_redis(config.address)
        user = await self._check_user(redis, credentials)
        if config.select is not None:
            await redis.select(config.select)
        global_keys = config._global_keys
        namespace = await self._get_namespace(redis, global_keys, user)
        ns_keys = NamespaceKeys(global_keys, namespace)
        cl_keys = CleanupKeys(global_keys)
        mailbox_set = MailboxSet(redis, ns_keys, cl_keys)
        filter_set = FilterSet(redis, ns_keys)
        try:
            await mailbox_set.add_mailbox('INBOX')
        except ValueError:
            pass
        yield Session(redis, credentials.identity, config, self,
                      mailbox_set, filter_set)

    async def _check_user(self, redis: Redis,
                          credentials: AuthenticationCredentials) -> str:
        if not isinstance(credentials, ExternalResult):
            user = credentials.authcid
            data = await self._get_user(redis, user)
            if data is None:
                raise InvalidAuth()
            await data.check_password(credentials)
            if user != credentials.identity:
                raise InvalidAuth(authorization=True)
        return credentials.identity

    async def _get_user(self, redis: Redis, user: str) \
            -> Optional[UserMetadata]:
        user_bytes = user.encode('utf-8')
        user_key = self.config._users_root.end(user_bytes)
        if self.config.users_json:
            json_data = await redis.get(user_key)
            if json_data is None:
                return None
            data_dict = json.loads(json_data)
        else:
            data_dict = await redis.hgetall(user_key, encoding='utf-8')
            if data_dict is None:
                return None
        return UserMetadata.from_dict(self.config, data_dict)

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
