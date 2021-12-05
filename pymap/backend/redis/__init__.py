
from __future__ import annotations

import json
import logging
import uuid
from argparse import ArgumentParser, Namespace
from asyncio import CancelledError
from collections.abc import Awaitable, Callable, Mapping, AsyncIterator
from contextlib import asynccontextmanager, suppress, AsyncExitStack
from datetime import datetime
from secrets import token_bytes
from typing import Any, Optional, Final

from aioredis import Redis, ConnectionError
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

from .background import BackgroundAction, BackgroundTask, NoopAction
from .cleanup import CleanupAction
from .filter import FilterSet
from .keys import DATA_VERSION, RedisKey, GlobalKeys, CleanupKeys, \
    NamespaceKeys
from .mailbox import Message, MailboxSet
from ..session import BaseSession

__all__ = ['RedisBackend', 'Config', 'Session']

_log = logging.getLogger(__name__)

_Connect = Callable[[], Awaitable[Redis]]


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
        parser.add_argument('--data-address', metavar='URL',
                            help='the redis server address for mail data,'
                            ' if different')
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
        status = HealthStatus(name='redis')
        login = Login(config, status)
        return cls(login, config, status), config

    async def start(self, stack: AsyncExitStack) -> None:
        config = self._config
        global_keys = config._global_keys
        self.status.set_healthy()
        user_action = NoopAction()
        mail_action = CleanupAction(global_keys)
        self.login._start_background(stack, user_action, mail_action)


class Config(IMAPConfig):
    """The config implementation for the redis backend.

    Args:
        args: The command-line arguments.
        address: The redis server address.
        data_address: The redis server address for mail data, if different.
        separator: The redis key segment separator.
        prefix: The prefix for mail data keys.
        users_prefix: The user lookup key prefix.
        users_json: True if the user lookup value contains JSON.

    """

    def __init__(self, args: Namespace, *, address: str,
                 data_address: Optional[str],
                 separator: bytes, prefix: bytes, users_prefix: bytes,
                 users_json: bool, **extra: Any) -> None:
        super().__init__(args, admin_key=token_bytes(), **extra)
        self._address = address
        self._data_address = data_address
        self._separator = separator
        self._prefix = prefix
        self._users_prefix = users_prefix
        self._users_json = users_json

    @property
    def backend_capability(self) -> BackendCapability:
        return BackendCapability(idle=True, object_id=True, multi_append=True)

    @property
    def address(self) -> str:
        """The redis server address for user data. Defaults to a connection to
        localhost.

        See Also:
            :func:`aioredis.create_connection`

        """
        return self._address

    @property
    def data_address(self) -> str:
        """The redis server address for mail data. Defaults to a connection to
        localhost.

        See Also:
            :func:`aioredis.create_connection`

        """
        if self._data_address is not None:
            return self._data_address
        else:
            return self.address

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
                'data_address': args.data_address,
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

    def __init__(self, config: Config, status: HealthStatus) -> None:
        super().__init__()
        self._config = config
        self._tokens = AllTokens()
        self._user_redis = Redis.from_url(config.address)
        self._user_status = status.new_dependency(False, name='user')
        self._mail_redis = Redis.from_url(config.data_address)
        self._mail_status = status.new_dependency(False, name='mail')

    @property
    def tokens(self) -> TokensInterface:
        return self._tokens

    @classmethod
    async def _connect(cls, stack: AsyncExitStack,
                       redis: Redis, status: HealthStatus) -> Redis:
        try:
            conn = await stack.enter_async_context(redis.client())
        except (ConnectionError, OSError) as exc:
            is_debug = _log.isEnabledFor(logging.DEBUG)
            _log.warn('%s: %s', type(exc).__name__, exc, exc_info=is_debug)
            status.set_unhealthy()
            raise CancelledError() from exc
        else:
            status.set_healthy()
            return conn

    async def _user_connect(self) -> Redis:
        return await self._connect(connection_exit.get(),
                                   self._user_redis, self._user_status)

    async def _mail_connect(self) -> Redis:
        return await self._connect(connection_exit.get(),
                                   self._mail_redis, self._mail_status)

    def _start_background(self, stack: AsyncExitStack,
                          user_action: BackgroundAction,
                          mail_action: BackgroundAction) -> None:
        user_background = BackgroundTask(self._user_redis, self._user_status,
                                         user_action)
        mail_background = BackgroundTask(self._mail_redis, self._mail_status,
                                         mail_action)
        user_task = user_background.start()
        mail_task = mail_background.start()
        stack.callback(user_task.cancel)
        stack.callback(mail_task.cancel)

    async def _check(self) -> None:
        async with AsyncExitStack() as stack:
            with suppress(Exception):
                await self._connect(stack, self._user_redis, self._user_status)
            with suppress(Exception):
                await self._connect(stack, self._mail_redis, self._mail_status)

    async def authenticate(self, credentials: AuthenticationCredentials) \
            -> Identity:
        config = self._config
        authcid = credentials.authcid
        token_key: Optional[bytes] = None
        role: Optional[str] = None
        if credentials.authcid_type == 'admin-token':
            authcid = credentials.identity
            role = 'admin'
        try:
            authcid_identity = Identity(config, self.tokens,
                                        self._user_connect, self._mail_connect,
                                        authcid)
            metadata = await authcid_identity.get()
        except UserNotFound:
            metadata = UserMetadata(config)
        if 'key' in metadata.params:
            token_key = bytes.fromhex(metadata.params['key'])
        role = role or metadata.role
        await metadata.check_password(credentials, token_key=token_key)
        if role != 'admin' and authcid != credentials.identity:
            raise AuthorizationFailure()
        return Identity(config, self.tokens,
                        self._user_connect, self._mail_connect,
                        credentials.identity, role)


class Identity(IdentityInterface):
    """The identity implementation for the redis backend."""

    def __init__(self, config: Config, tokens: TokensInterface,
                 user_connect: _Connect, mail_connect: _Connect,
                 name: str, role: str = None) -> None:
        super().__init__()
        self.config: Final = config
        self.tokens: Final = tokens
        self._user_connect = user_connect
        self._mail_connect = mail_connect
        self._name = name
        self._role = role

    @property
    def name(self) -> str:
        return self._name

    async def new_token(self, *, expiration: datetime = None) -> Optional[str]:
        metadata = await self.get()
        if 'key' not in metadata.params:
            return None
        key = bytes.fromhex(metadata.params['key'])
        return self.tokens.get_login_token(self.name, key)

    @asynccontextmanager
    async def new_session(self) -> AsyncIterator[Session]:
        config = self.config
        conn = await self._mail_connect()
        global_keys = config._global_keys
        namespace = await self._get_namespace(conn, global_keys, self.name)
        ns_keys = NamespaceKeys(global_keys, namespace)
        cl_keys = CleanupKeys(global_keys)
        mailbox_set = MailboxSet(conn, ns_keys, cl_keys)
        filter_set = FilterSet(conn, ns_keys)
        try:
            await mailbox_set.add_mailbox('INBOX')
        except ValueError:
            pass
        yield Session(conn, self.name, config, mailbox_set, filter_set)

    async def _get_namespace(self, conn: Redis, global_keys: GlobalKeys,
                             user: str) -> bytes:
        user_key = user.encode('utf-8')
        new_namespace = uuid.uuid4().hex.encode('ascii')
        ns_val = b'%d/%b' % (DATA_VERSION, new_namespace)
        async with conn.pipeline() as multi:
            multi.hsetnx(global_keys.namespaces, user_key, ns_val)
            multi.hget(global_keys.namespaces, user_key)
            _, ns_val = await multi.execute()
        version, namespace = ns_val.split(b'/', 1)
        if int(version) != DATA_VERSION:
            raise IncompatibleData()
        return namespace

    async def get(self) -> UserMetadata:
        conn = await self._user_connect()
        user_bytes = self.name.encode('utf-8')
        user_key = self.config._users_root.end(user_bytes)
        if self.config.users_json:
            json_data = await conn.get(user_key)
            if json_data is None:
                raise UserNotFound(self.name)
            data_dict = json.loads(json_data)
        else:
            data_dict = await conn.hgetall(user_key)
            if data_dict is None:
                raise UserNotFound(self.name)
        return UserMetadata(self.config, **data_dict)

    async def set(self, metadata: UserMetadata) -> None:
        config = self.config
        conn = await self._user_connect()
        if self._role != 'admin' and metadata.role:
            raise NotAllowedError('Cannot assign role.')
        user_key = config._users_root.end(self.name.encode('utf-8'))
        user_dict = metadata.to_dict(key=token_bytes().hex())
        if self.config.users_json:
            json_data = json.dumps(user_dict)
            await conn.set(user_key, json_data)
        else:
            async with conn.pipeline() as multi:
                multi.delete(user_key)
                multi.hmset(user_key, user_dict)
                await multi.execute()

    async def delete(self) -> None:
        config = self.config
        conn = await self._user_connect()
        user_key = config._users_root.end(self.name.encode('utf-8'))
        if not await conn.delete(user_key):
            raise UserNotFound(self.name)
