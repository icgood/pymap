
from __future__ import annotations

import asyncio
import json
import uuid
from argparse import Namespace
from asyncio import Task
from contextlib import closing, asynccontextmanager
from functools import partial
from typing import Any, Optional, Tuple, Mapping, AsyncIterator

from aioredis import create_redis, Redis  # type: ignore
from pysasl import AuthenticationCredentials

from pymap.bytes import BytesFormat
from pymap.config import BackendCapability, IMAPConfig
from pymap.context import connection_exit
from pymap.exceptions import InvalidAuth, IncompatibleData, MailboxConflict
from pymap.interfaces.backend import BackendInterface
from pymap.interfaces.session import LoginProtocol

from .cleanup import Cleanup, CleanupTask
from .filter import FilterSet
from .keys import DATA_VERSION, RedisKey, GlobalKeys, NamespaceKeys
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

    def __init__(self, login: LoginProtocol, config: Config) -> None:
        super().__init__()
        self._login = login
        self._config = config
        self._task = asyncio.create_task(self._run())

    @property
    def login(self) -> LoginProtocol:
        return self._login

    @property
    def config(self) -> Config:
        return self._config

    @property
    def task(self) -> Task:
        return self._task

    async def _run(self) -> None:
        config = self._config
        global_keys = config._global_keys
        connect_redis = partial(create_redis, config.address)
        await CleanupTask(connect_redis, global_keys).run_forever()

    @classmethod
    def add_subparser(cls, name: str, subparsers) -> None:
        parser = subparsers.add_parser(name, help='redis backend')
        parser.add_argument('address', nargs='?', default='redis://localhost',
                            help='the redis server address')
        parser.add_argument('--select', metavar='DB', type=int,
                            help='the redis database for mail data')
        parser.add_argument('--separator', metavar='CHAR', default='/',
                            help='the redis key segment separator')
        parser.add_argument('--prefix', metavar='VAL', default='',
                            help='the mail data key prefix')
        parser.add_argument('--users-prefix', metavar='VAL', default='',
                            help='the user lookup key prefix')
        parser.add_argument('--users-json', action='store_true',
                            help='the user lookup value contains JSON')

    @classmethod
    async def init(cls, args: Namespace) -> Tuple[RedisBackend, Config]:
        config = Config.from_args(args)
        return cls(Session.login, config), config


class Config(IMAPConfig):
    """The config implementation for the redis backend.

    Args:
        args: The command-line arguments.
        address: The redis server address.
        select: The redis database for mail data.
        separator: The redis key segment separator.
        prefix: The prefix for mail data keys.
        users_prefix: The user lookup key template.
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
        return {'address': args.address,
                'select': args.select,
                'separator': args.separator.encode('utf-8'),
                'prefix': args.prefix.encode('utf-8'),
                'users_prefix': args.users_prefix.encode('utf-8'),
                'users_json': args.users_json}


class Session(BaseSession[Message]):
    """The session implementation for the redis backend."""

    resource = __name__

    _namespace_key = 'pymap:namespace'
    _version_key = 'pymap:dataversion'

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

    @classmethod
    async def _connect_redis(cls, address: str) -> Redis:
        redis = await create_redis(address)
        stack = connection_exit.get()
        stack.enter_context(closing(redis))
        return redis

    @classmethod
    @asynccontextmanager
    async def login(cls, credentials: AuthenticationCredentials,
                    config: Config) -> AsyncIterator[Session]:
        """Checks the given credentials for a valid login and returns a new
        session.

        """
        redis = await cls._connect_redis(config.address)
        user = await cls._check_user(redis, config, credentials)
        if config.select is not None:
            await redis.select(config.select)
        global_keys = config._global_keys
        namespace = await cls._get_namespace(redis, global_keys, user)
        ns_keys = NamespaceKeys(global_keys, namespace)
        cleanup = Cleanup(global_keys)
        mailbox_set = MailboxSet(redis, ns_keys, cleanup)
        try:
            await mailbox_set.add_mailbox('INBOX')
        except MailboxConflict:
            pass
        filter_set = FilterSet(redis, ns_keys)
        yield cls(redis, credentials.identity, config, mailbox_set, filter_set)

    @classmethod
    async def _check_user(cls, redis: Redis, config: Config,
                          credentials: AuthenticationCredentials) -> str:
        user = credentials.authcid
        password = await cls._get_password(redis, config, user)
        if user != credentials.identity:
            raise InvalidAuth()
        elif ldap_context is None or not credentials.has_secret:
            if not credentials.check_secret(password):
                raise InvalidAuth()
        elif not ldap_context.verify(credentials.secret, password):
            raise InvalidAuth()
        return user

    @classmethod
    async def _get_password(cls, redis: Redis, config: Config,
                            user: str) -> str:
        user_key = config._users_root.end(user.encode('utf-8'))
        if config.users_json:
            json_data = await redis.get(user_key)
            if json_data is None:
                raise InvalidAuth()
            try:
                json_obj = json.loads(json_data)
                return json_obj['password']
            except Exception as exc:
                raise InvalidAuth() from exc
        else:
            password, identity = await redis.hmget(
                user_key, b'password', b'identity')
            if password is None:
                raise InvalidAuth()
            return password.decode('utf-8')

    @classmethod
    async def _get_namespace(cls, redis: Redis, global_keys: GlobalKeys,
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
