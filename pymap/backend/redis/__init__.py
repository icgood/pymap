
from __future__ import annotations

import asyncio
import json
import logging
import secrets
import uuid
from argparse import ArgumentParser, Namespace
from asyncio import CancelledError
from collections.abc import Awaitable, Callable, Mapping, Set, AsyncIterator
from contextlib import asynccontextmanager, suppress, AsyncExitStack
from datetime import datetime
from secrets import token_bytes
from typing import TypeAlias, Any, Final

from redis.asyncio import Redis
from pysasl.creds.server import ServerCredentials

from pymap.bytes import BytesFormat
from pymap.config import BackendCapability, IMAPConfig
from pymap.context import connection_exit
from pymap.exceptions import AuthorizationFailure, IncompatibleData, \
    NotAllowedError, UserNotFound
from pymap.health import HealthStatus
from pymap.interfaces.backend import BackendInterface
from pymap.interfaces.login import LoginInterface, IdentityInterface
from pymap.interfaces.token import TokenCredentials, TokensInterface
from pymap.token import AllTokens
from pymap.user import UserRoles, UserMetadata

from .background import BackgroundAction, BackgroundTask, NoopAction
from .cleanup import CleanupAction
from .filter import FilterSet
from .keys import DATA_VERSION, RedisKey, GlobalKeys, CleanupKeys, \
    NamespaceKeys
from .mailbox import Message, MailboxSet
from ..session import BaseSession

__all__ = ['RedisBackend', 'Config', 'Session']

_log = logging.getLogger(__name__)

_Connect: TypeAlias = Callable[[], Awaitable['Redis[bytes]']]


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
        parser: ArgumentParser = subparsers.add_parser(
            name, help='redis backend')
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

    """

    def __init__(self, args: Namespace, *, address: str,
                 data_address: str | None,
                 separator: bytes, prefix: bytes, users_prefix: bytes,
                 **extra: Any) -> None:
        super().__init__(args, admin_key=token_bytes(), **extra)
        self._address = address
        self._data_address = data_address
        self._separator = separator
        self._prefix = prefix
        self._users_prefix = users_prefix

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
                'users_prefix': args.users_prefix.encode('utf-8')}


class Session(BaseSession[Message]):
    """The session implementation for the redis backend."""

    resource = __name__

    def __init__(self, redis: Redis[bytes], owner: str, config: Config,
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
        self._tokens = AllTokens(config)
        self._user_redis = Redis.from_url(config.address)
        self._user_status = status.new_dependency(False, name='user')
        self._mail_redis = Redis.from_url(config.data_address)
        self._mail_status = status.new_dependency(False, name='mail')

    @property
    def tokens(self) -> TokensInterface:
        return self._tokens

    @classmethod
    async def _connect(cls, stack: AsyncExitStack, redis: Redis[bytes],
                       status: HealthStatus) \
            -> Redis[bytes]:
        try:
            conn = await stack.enter_async_context(redis.client())
        except OSError as exc:
            is_debug = _log.isEnabledFor(logging.DEBUG)
            _log.warn('%s: %s', type(exc).__name__, exc, exc_info=is_debug)
            status.set_unhealthy()
            raise CancelledError() from exc
        else:
            status.set_healthy()
            return conn

    async def _user_connect(self) -> Redis[bytes]:
        return await self._connect(connection_exit.get(),
                                   self._user_redis, self._user_status)

    async def _mail_connect(self) -> Redis[bytes]:
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

    async def authenticate(self, credentials: ServerCredentials) \
            -> Identity:
        config = self._config
        authcid = credentials.authcid
        authzid = credentials.authzid
        roles = UserRoles()
        if isinstance(credentials, TokenCredentials):
            authcid = credentials.identifier
            roles.add(credentials.role)
        try:
            authcid_identity = Identity(config, self.tokens,
                                        self._user_connect, self._mail_connect,
                                        authcid, roles)
            metadata: UserMetadata = await authcid_identity.get()
        except UserNotFound:
            await asyncio.sleep(self._config.invalid_user_sleep)
            metadata = UserMetadata(config, authcid)
        await metadata.check_password(credentials)
        roles |= metadata.roles
        if authcid != authzid and 'admin' not in roles:
            raise AuthorizationFailure()
        return Identity(config, self.tokens,
                        self._user_connect, self._mail_connect,
                        authzid, roles)


class Identity(IdentityInterface):
    """The identity implementation for the redis backend."""

    def __init__(self, config: Config, tokens: TokensInterface,
                 user_connect: _Connect, mail_connect: _Connect,
                 name: str, roles: Set[str]) -> None:
        super().__init__()
        self.config: Final = config
        self.tokens: Final = tokens
        self._user_connect = user_connect
        self._mail_connect = mail_connect
        self._name = name
        self._roles = roles

    @property
    def name(self) -> str:
        return self._name

    async def new_token(self, *, expiration: datetime | None = None) \
            -> str | None:
        user = await self.get()
        key = user.key
        if key is None:
            return None
        return self.tokens.get_login_token(self.name, self.name, key)

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

    async def _get_namespace(self, conn: Redis[bytes], global_keys: GlobalKeys,
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

    async def get(self) -> User:
        conn = await self._user_connect()
        user_bytes = self.name.encode('utf-8')
        user_key = self.config._users_root.end(user_bytes)
        json_data = await conn.get(user_key)
        if json_data is None:
            raise UserNotFound(self.name)
        data_dict: Mapping[str, str] = json.loads(json_data)
        return User._from_dict(self.config, self.name, data_dict)

    async def set(self, metadata: UserMetadata) -> None:
        config = self.config
        conn = await self._user_connect()
        params = self._params_with_key(metadata.params)
        user = User(self.config, metadata.authcid,
                    password=metadata.password, params=params)
        if 'admin' not in self._roles and user.roles:
            raise NotAllowedError('Cannot assign role.')
        user_key = config._users_root.end(self.name.encode('utf-8'))
        user_dict = user._to_dict()
        json_data = json.dumps(user_dict)
        await conn.set(user_key, json_data)

    async def delete(self) -> None:
        config = self.config
        conn = await self._user_connect()
        user_key = config._users_root.end(self.name.encode('utf-8'))
        if not await conn.delete(user_key):
            raise UserNotFound(self.name)

    @classmethod
    def _params_with_key(cls, params: Mapping[str, str] | None) \
            -> Mapping[str, str]:
        if params is None:
            return {'key': secrets.token_hex()}
        elif 'key' not in params:
            return dict(params, key=secrets.token_hex())
        else:
            return params


class User(UserMetadata):

    @classmethod
    def _from_dict(cls, config: IMAPConfig, authcid: str,
                   data: Mapping[str, str]) -> User:
        match data:
            case {'password': password, **params}:
                return cls(config, authcid, password=password, params=params)
            case params:
                return cls(config, authcid, params=params)

    def _to_dict(self) -> Mapping[str, str]:
        ret = dict(self.params)
        if self.password is not None:
            ret['password'] = self.password
        return ret

    @property
    def roles(self) -> UserRoles:
        return UserRoles([self.params.get('role')])

    @property
    def key(self) -> bytes | None:
        key = self.params.get('key')
        if key is not None:
            return bytes.fromhex(key)
        else:
            return None

    def get_key(self, identifier: str) -> bytes | None:
        if identifier != self.authcid:
            return None
        return self.key
