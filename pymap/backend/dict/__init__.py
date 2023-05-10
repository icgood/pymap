
from __future__ import annotations

import asyncio
import dataclasses
import os.path
import uuid
from argparse import ArgumentParser, Namespace
from collections.abc import Set, Mapping, AsyncIterator
from contextlib import closing, asynccontextmanager, AsyncExitStack
from datetime import datetime, timezone
from importlib.resources import files
from secrets import token_bytes
from typing import Any, Final

from pysasl.creds.server import ServerCredentials

from pymap.config import BackendCapability, IMAPConfig
from pymap.exceptions import AuthorizationFailure, InvalidAuth, \
    NotAllowedError, UserNotFound
from pymap.health import HealthStatus
from pymap.interfaces.backend import BackendInterface
from pymap.interfaces.login import LoginInterface, IdentityInterface
from pymap.interfaces.token import TokenCredentials
from pymap.parsing.message import AppendMessage
from pymap.parsing.specials.flag import Flag, Recent
from pymap.token import AllTokens
from pymap.user import Passwords, UserMetadata

from .filter import FilterSet
from .mailbox import Message, MailboxData, MailboxSet
from ..session import BaseSession

__all__ = ['DictBackend', 'Config']


class DictBackend(BackendInterface):
    """Defines a backend that uses an in-memory dictionary for example usage
    and integration testing.

    """

    def __init__(self, login: Login, config: Config) -> None:
        super().__init__()
        self._login = login
        self._config = config
        self._status = HealthStatus()

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
            name, help='in-memory backend')
        parser.add_argument('--demo-data', action='store_true',
                            help='load initial demo data')
        parser.add_argument('--demo-user', default='demouser',
                            metavar='VAL', help='demo user ID')
        parser.add_argument('--demo-password', default='demopass',
                            metavar='VAL', help='demo user password')
        return parser

    @classmethod
    async def init(cls, args: Namespace, **overrides: Any) \
            -> tuple[DictBackend, Config]:
        config = Config.from_args(args, **overrides)
        login = Login(config)
        await cls._add_demo_user(config, login)
        return cls(login, config), config

    @classmethod
    async def _add_demo_user(cls, config: Config, login: Login) -> None:
        hashed_password = await Passwords(config).hash_password(
            config.demo_password)
        demo_user = UserMetadata(config, config.demo_user,
                                 password=hashed_password)
        await login.demo_user_identity.set(demo_user)

    async def start(self, stack: AsyncExitStack) -> None:
        pass


class Config(IMAPConfig):
    """The config implementation for the dict backend."""

    def __init__(self, args: Namespace, *, demo_data: bool,
                 demo_user: str, demo_password: str,
                 demo_data_resource: str = __name__,
                 admin_key: bytes | None = None, **extra: Any) -> None:
        admin_key = admin_key or token_bytes()
        super().__init__(args, admin_key=admin_key, **extra)
        self._demo_data = demo_data
        self._demo_user = demo_user
        self._demo_password = demo_password
        self._demo_data_resource = demo_data_resource
        self.set_cache: dict[str, tuple[MailboxSet, FilterSet]] = {}

    @property
    def backend_capability(self) -> BackendCapability:
        return BackendCapability(idle=True, object_id=True, multi_append=True)

    @property
    def demo_data(self) -> bool:
        """True if demo data should be loaded at startup."""
        return self._demo_data

    @property
    def demo_data_resource(self) -> str:
        """Resource path of demo data files."""
        return self._demo_data_resource

    @property
    def demo_user(self) -> str:
        """A login name that is valid at startup, which defaults to
        ``demouser``.

        """
        return self._demo_user

    @property
    def demo_password(self) -> str:
        """The password for the :attr:`.demo_user` login name, which defaults
        to ``demopass``.

        """
        return self._demo_password

    @classmethod
    def parse_args(cls, args: Namespace) -> Mapping[str, Any]:
        return {**super().parse_args(args),
                'demo_data': args.demo_data,
                'demo_user': args.demo_user,
                'demo_password': args.demo_password}


class Session(BaseSession[Message]):
    """The session implementation for the dict backend."""

    def __init__(self, owner: str, config: Config, mailbox_set: MailboxSet,
                 filter_set: FilterSet) -> None:
        super().__init__(owner)
        self._config = config
        self._mailbox_set = mailbox_set
        self._filter_set = filter_set

    @property
    def config(self) -> Config:
        return self._config

    @property
    def mailbox_set(self) -> MailboxSet:
        return self._mailbox_set

    @property
    def filter_set(self) -> FilterSet:
        return self._filter_set


class Login(LoginInterface):
    """The login implementation for the dict backend."""

    def __init__(self, config: Config) -> None:
        super().__init__()
        self.config: Final = config
        self.users_dict: dict[str, UserMetadata] = {}
        self.tokens_dict: dict[str, tuple[str, bytes]] = {}
        self._passwords = Passwords(config)
        self._tokens = AllTokens(config)

    @property
    def tokens(self) -> AllTokens:
        return self._tokens

    @property
    def demo_user_identity(self) -> Identity:
        return Identity(self.config.demo_user, self, None, frozenset())

    async def authenticate(self, credentials: ServerCredentials) -> Identity:
        authcid = credentials.authcid
        roles: set[str] = set()
        token_id: str | None = None
        if isinstance(credentials, TokenCredentials):
            token_id = credentials.identifier
            roles.update(credentials.roles)
        identity = Identity(authcid, self, token_id, roles)
        try:
            user = await identity.get()
        except UserNotFound:
            await asyncio.sleep(self.config.invalid_user_sleep)
            user = UserMetadata(self.config, authcid)
        if not await self._passwords.check_password(user, credentials):
            raise InvalidAuth()
        roles |= user.roles
        return identity

    async def authorize(self, authenticated: IdentityInterface, authzid: str) \
            -> Identity:
        authcid = authenticated.name
        roles = authenticated.roles
        if authcid != authzid and 'admin' not in roles:
            raise AuthorizationFailure()
        return Identity(authzid, self, None, roles)


class Identity(IdentityInterface):
    """The identity implementation for the dict backend."""

    def __init__(self, name: str, login: Login, token_id: str | None,
                 roles: Set[str]) -> None:
        super().__init__()
        self.login: Final = login
        self.config: Final = login.config
        self._name = name
        self._roles = roles
        self._token_id = token_id

    @property
    def name(self) -> str:
        return self._name

    @property
    def roles(self) -> frozenset[str]:
        return frozenset(self._roles)

    async def new_token(self, *, expiration: datetime | None = None) \
            -> str | None:
        token_id = uuid.uuid4().hex
        token_key = token_bytes()
        self.login.tokens_dict[token_id] = (self.name, token_key)
        return self.login.tokens.get_login_token(
            token_id, self.name, token_key, expiration=expiration)

    @asynccontextmanager
    async def new_session(self) -> AsyncIterator[Session]:
        identity = self.name
        config = self.config
        _ = await self.get()
        mailbox_set, filter_set = config.set_cache.get(identity, (None, None))
        if not mailbox_set or not filter_set:
            mailbox_set = MailboxSet()
            filter_set = FilterSet()
            if config.demo_data and identity == config.demo_user:
                await self._load_demo(config.demo_data_resource,
                                      mailbox_set, filter_set)
            config.set_cache[identity] = (mailbox_set, filter_set)
        yield Session(identity, config, mailbox_set, filter_set)

    async def _load_demo(self, resource: str, mailbox_set: MailboxSet,
                         filter_set: FilterSet) -> None:
        inbox = await mailbox_set.get_mailbox('INBOX')
        await self._load_demo_mailbox(resource, 'INBOX', inbox)
        mbx_names = sorted(f.name
                           for f in files(resource).joinpath('demo').iterdir()
                           if f.is_dir())
        await self._load_demo_sieve(resource, filter_set)
        for name in mbx_names:
            if name != 'INBOX':
                await mailbox_set.add_mailbox(name)
                mbx = await mailbox_set.get_mailbox(name)
                await self._load_demo_mailbox(resource, name, mbx)

    async def _load_demo_sieve(self, resource: str,
                               filter_set: FilterSet) -> None:
        path = os.path.join('demo', 'sieve')
        sieve = files(resource).joinpath(path).read_bytes()
        await filter_set.put('demo', sieve)
        await filter_set.set_active('demo')

    async def _load_demo_mailbox(self, resource: str, name: str,
                                 mbx: MailboxData) -> None:
        path = os.path.join('demo', name)
        msg_names = sorted(f.name
                           for f in files(resource).joinpath(path).iterdir()
                           if f.is_file())
        for msg_name in msg_names:
            if msg_name == '.readonly':
                mbx._readonly = True
                continue
            elif msg_name.startswith('.'):
                continue
            msg_path = os.path.join(path, msg_name)
            with closing(files(resource).joinpath(msg_path).open('rb')) \
                    as msg_stream:
                flags_line = msg_stream.readline()
                msg_timestamp = float(msg_stream.readline())
                msg_data = msg_stream.read()
            msg_dt = datetime.fromtimestamp(msg_timestamp, timezone.utc)
            msg_flags = {Flag(flag) for flag in flags_line.split()}
            if Recent in msg_flags:
                msg_flags.remove(Recent)
                msg_recent = True
            else:
                msg_recent = False
            append_msg = AppendMessage(msg_data, msg_dt, frozenset(msg_flags))
            await mbx.append(append_msg, recent=msg_recent)

    async def get(self) -> UserMetadata:
        token_id = self._token_id
        name = self.name
        token_key: bytes | None = None
        if token_id is not None:
            try:
                name, token_key = self.login.tokens_dict[token_id]
            except KeyError as exc:
                raise UserNotFound() from exc
            else:
                self._name = name
        user = self.login.users_dict.get(name)
        if user is None:
            raise UserNotFound(self.name)
        return dataclasses.replace(user, token_key=token_key)

    async def set(self, user: UserMetadata) -> None:
        if 'admin' not in self._roles and user.roles:
            raise NotAllowedError('Cannot assign roles.')
        self.login.users_dict[self.name] = user

    async def delete(self) -> None:
        try:
            del self.login.users_dict[self.name]
        except KeyError as exc:
            raise UserNotFound(self.name) from exc
        self.config.set_cache.pop(self.name, None)
        for token_id, (name, _) in list(self.login.tokens_dict.items()):
            if name == self.name:
                del self.login.tokens_dict[token_id]
