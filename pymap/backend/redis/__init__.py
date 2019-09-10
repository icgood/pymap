
from __future__ import annotations

import asyncio
import json
import uuid
from argparse import Namespace, ArgumentDefaultsHelpFormatter
from asyncio import Task
from contextlib import closing, asynccontextmanager
from functools import partial
from typing import Any, Optional, Tuple, Mapping, AsyncIterator

from aioredis import create_redis, Redis, MultiExecError  # type: ignore
from pysasl import AuthenticationCredentials

from pymap.config import BackendCapability, IMAPConfig
from pymap.context import connection_exit
from pymap.exceptions import InvalidAuth, IncompatibleData, MailboxConflict
from pymap.interfaces.backend import BackendInterface
from pymap.interfaces.session import LoginProtocol

from ._util import check_errors
from .cleanup import Cleanup, CleanupTask
from .filter import FilterSet
from .keys import DATA_VERSION, RedisKey, NamespaceKeys
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
        root = config._root
        connect_redis = partial(create_redis, config.address)
        await CleanupTask(connect_redis, root).run_forever()

    @classmethod
    def add_subparser(cls, name: str, subparsers) -> None:
        parser = subparsers.add_parser(
            name, help='redis backend',
            formatter_class=ArgumentDefaultsHelpFormatter)
        parser.add_argument('address', nargs='?', default='redis://localhost',
                            help='the redis server address')
        parser.add_argument('--select', metavar='DB', type=int,
                            help='the redis database for mail data')
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
        prefix: The prefix for mail data keys.
        users_prefix: The user lookup key template.
        users_json: True if the user lookup value contains JSON.

    """

    def __init__(self, args: Namespace, *, address: str, select: Optional[int],
                 prefix: bytes, users_prefix: bytes, users_json: bool,
                 **extra: Any) -> None:
        super().__init__(args, **extra)
        self._address = address
        self._select = select
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
    def _root(self) -> RedisKey:
        return RedisKey(self.prefix, {})

    @property
    def _users_root(self) -> RedisKey:
        return RedisKey(self.users_prefix, {}).fork(b':%(user)s')

    @classmethod
    def parse_args(cls, args: Namespace) -> Mapping[str, Any]:
        return {'address': args.address,
                'select': args.select,
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
        namespace = await cls._check_user(redis, config, credentials)
        if config.select is not None:
            await redis.select(config.select)
        root = config._root
        ns_keys = NamespaceKeys(root, namespace)
        cleanup = Cleanup(root)
        mailbox_set = MailboxSet(redis, ns_keys, cleanup)
        try:
            await mailbox_set.add_mailbox('INBOX')
        except MailboxConflict:
            pass
        filter_set = FilterSet(redis, namespace)
        yield cls(redis, credentials.identity, config, mailbox_set, filter_set)

    @classmethod
    async def _check_user(cls, redis: Redis, config: Config,
                          credentials: AuthenticationCredentials) -> bytes:
        user = credentials.authcid
        key = config._users_root.end(user=user.encode('utf-8'))
        if config.users_json:
            password, namespace = await cls._get_json(redis, key)
        else:
            password, namespace = await cls._get_hash(redis, key)
        if user != credentials.identity:
            raise InvalidAuth()
        elif ldap_context is None or not credentials.has_secret:
            if not credentials.check_secret(password):
                raise InvalidAuth()
        elif not ldap_context.verify(credentials.secret, password):
            raise InvalidAuth()
        return namespace

    @classmethod
    async def _get_json(cls, redis: Redis, user_key: bytes) \
            -> Tuple[str, bytes]:
        while True:
            await redis.watch(user_key)
            json_data = await redis.get(user_key)
            if json_data is None:
                raise InvalidAuth()
            json_obj = json.loads(json_data)
            try:
                password = json_obj['password']
            except KeyError as exc:
                raise InvalidAuth() from exc
            namespace: str = json_obj.get(cls._namespace_key)
            version: int = json_obj.get(cls._version_key, 0)
            if namespace is not None:
                break
            else:
                new_namespace = uuid.uuid4().hex
                json_obj[cls._namespace_key] = namespace = new_namespace
                json_obj[cls._version_key] = version = DATA_VERSION
                json_data = json.dumps(json_obj)
                multi = redis.multi_exec()
                multi.set(user_key, json_data)
                try:
                    await multi.execute()
                except MultiExecError:
                    if await check_errors(multi):
                        raise
                else:
                    break
        if version < DATA_VERSION:
            raise IncompatibleData()
        return password, namespace.encode('utf-8')

    @classmethod
    async def _get_hash(cls, redis: Redis, user_key: bytes) \
            -> Tuple[str, bytes]:
        password_bytes, namespace, data_version = await redis.hmget(
            user_key, b'password', cls._namespace_key, cls._version_key)
        if password_bytes is None:
            raise InvalidAuth()
        password = password_bytes.decode('utf-8')
        if namespace is None:
            namespace, version = await cls._update_hash(redis, user_key)
        else:
            version = int(data_version)
        if version < DATA_VERSION:
            raise IncompatibleData()
        return password, namespace

    @classmethod
    async def _update_hash(cls, redis: Redis, user_key: bytes) \
            -> Tuple[bytes, int]:
        new_namespace = uuid.uuid4().hex.encode('ascii')
        multi = redis.multi_exec()
        multi.hsetnx(user_key, cls._namespace_key, new_namespace)
        multi.hsetnx(user_key, cls._version_key, DATA_VERSION)
        multi.hmget(user_key, cls._namespace_key, cls._version_key)
        _, _, (namespace, data_version) = await multi.execute()
        return namespace, int(data_version)
