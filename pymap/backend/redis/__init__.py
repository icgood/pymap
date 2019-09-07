
from __future__ import annotations

import asyncio
import json
import uuid
from argparse import Namespace, ArgumentDefaultsHelpFormatter
from asyncio import Task
from contextlib import closing, asynccontextmanager
from typing import Any, Optional, Tuple, Mapping, AsyncIterator

from aioredis import create_redis, Redis  # type: ignore
from pysasl import AuthenticationCredentials

from pymap.config import BackendCapability, IMAPConfig
from pymap.context import connection_exit
from pymap.exceptions import InvalidAuth, MailboxConflict
from pymap.interfaces.backend import BackendInterface
from pymap.interfaces.session import LoginProtocol

from .cleanup import Cleanup, CleanupTask
from .filter import FilterSet
from .keys import RedisKey, NamespaceKeys
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
        redis = await create_redis(config.address)
        with closing(redis):
            await CleanupTask(redis, root).run()

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
                            help='the prefix for redis keys')
        parser.add_argument('--users-hash', metavar='KEY',
                            help='the hash key for user lookup')
        parser.add_argument('--users-key', metavar='FORMAT', default='{name}',
                            help='the user lookup key template')
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
        users_hash: The hash key for user lookup.
        users_key: The user lookup key template.
        users_json: True if the user lookup value contains JSON.

    """

    def __init__(self, args: Namespace, *, address: str,
                 select: Optional[int], prefix: str,
                 users_hash: Optional[str], users_key: str,
                 users_json: bool, **extra: Any) -> None:
        super().__init__(args, **extra)
        self._address = address
        self._select = select
        self._prefix = prefix
        self._users_hash = users_hash
        self._users_key = users_key
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
    def prefix(self) -> str:
        """The prefix for mail data keys. This prefix does not apply to user
        lookup, e.g. :attr:`.users_hash`, :attr:`.users_key`, or
        :attr:`.namespace_hash`.

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
    def namespace_hash(self) -> str:
        """The name of a hash used to specify user namespace prefixes.

        Typically, when a user first logs in it is assigned a random hex string
        used to namespace all the keys related to its mailbox data. That means
        another user name can be assigned the same string, to share the mailbox
        or rename it.

        """
        prefix = self.users_hash or ''
        return f'{prefix}:namespace'

    @property
    def _root(self) -> RedisKey:
        prefix_bytes = self.prefix.encode('utf-8')
        return RedisKey(prefix_bytes, {})

    @classmethod
    def parse_args(cls, args: Namespace) -> Mapping[str, Any]:
        return {'address': args.address,
                'select': args.select,
                'prefix': args.prefix,
                'users_hash': args.users_hash,
                'users_key': args.users_key,
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
        password, namespace = await cls._get_password(redis, config, user)
        if user != credentials.identity:
            raise InvalidAuth()
        elif ldap_context is None or not credentials.has_secret:
            if not credentials.check_secret(password):
                raise InvalidAuth()
        elif not ldap_context.verify(credentials.secret, password):
            raise InvalidAuth()
        return namespace

    @classmethod
    async def _get_password(cls, redis: Redis, config: Config,
                            name: str) -> Tuple[str, bytes]:
        key = config.users_key.format(name=name)
        multi = redis.multi_exec()
        if config.users_hash is None:
            multi.get(key)
        else:
            multi.hget(config.users_hash, key)
        new_namespace = uuid.uuid4().hex.encode('ascii')
        multi.hsetnx(config.namespace_hash, key, new_namespace)
        multi.hget(config.namespace_hash, key)
        value, _, namespace = await multi.execute()
        if value is None:
            raise InvalidAuth()
        elif config.users_json:
            value_obj = json.loads(value)
            try:
                return value_obj['password'], namespace
            except KeyError as exc:
                raise InvalidAuth() from exc
        else:
            return value.decode('utf-8'), namespace
