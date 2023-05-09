
from __future__ import annotations

import asyncio
import os.path
import secrets
import uuid
from argparse import Action, ArgumentParser, Namespace
from collections.abc import Mapping, AsyncIterator, Set
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager, AsyncExitStack
from datetime import datetime
from typing import Any, Final

from pysasl.creds.server import ServerCredentials

from pymap.concurrent import Subsystem
from pymap.config import BackendCapability, IMAPConfig
from pymap.exceptions import AuthorizationFailure, InvalidAuth, \
    NotAllowedError, UserNotFound
from pymap.filter import PluginFilterSet, SingleFilterSet
from pymap.frozen import frozendict
from pymap.health import HealthStatus
from pymap.interfaces.backend import BackendInterface
from pymap.interfaces.login import LoginInterface, IdentityInterface
from pymap.interfaces.token import TokenCredentials, TokensInterface
from pymap.token import AllTokens
from pymap.user import Passwords, UserMetadata

from .layout import MaildirLayout
from .mailbox import Message, Maildir, MailboxSet
from .users import UsersFile, PasswordsFile, TokensFile, GroupsFile
from ..session import BaseSession

__all__ = ['MaildirBackend', 'Config']


class MaildirBackend(BackendInterface):
    """Defines an on-disk backend that uses :class:`~mailbox.Maildir` for
    mailbox storage and `MailboxFormat/Maildir
    <https://wiki2.dovecot.org/MailboxFormat/Maildir>`_ for metadata storage.

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
            name, help='on-disk backend')
        parser.add_argument('base_dir', metavar='DIR', action=_BaseDirAction,
                            help='base directory for mailbox relative paths')
        parser.add_argument('--concurrency', metavar='NUM', type=int,
                            help='maximum number of IO workers')
        parser.add_argument('--layout', metavar='TYPE', default='++',
                            help='maildir directory layout')
        parser.add_argument('--colon', metavar='CHAR', default=None,
                            help='info delimiter in mail filename')
        return parser

    @classmethod
    async def init(cls, args: Namespace, **overrides: Any) \
            -> tuple[MaildirBackend, Config]:
        config = Config.from_args(args)
        login = Login(config)
        if not os.path.exists(config.base_dir):
            os.mkdir(config.base_dir)
        return cls(login, config), config

    async def start(self, stack: AsyncExitStack) -> None:
        pass


class _BaseDirAction(Action):

    def __call__(self, parser: ArgumentParser, namespace: Namespace,
                 values: Any, option_string: str | None = None) -> None:
        assert isinstance(values, str)
        if os.path.isfile(values):
            raise parser.error(
                f'{self.metavar} argument {values!r} must not be a file')
        setattr(namespace, self.dest, values)


class Config(IMAPConfig):
    """The config implementation for the maildir backend.

    Args:
        args: The command-line arguments.
        base_dir: The base directory for all relative mailbox paths.
        layout: The Maildir directory layout.
        colon: The info delimiter in mail filename.
        hash_interface: The hash algorithm to use for passwords.

    """

    def __init__(self, args: Namespace, *, base_dir: str,
                 layout: str, colon: str | None,
                 **extra: Any) -> None:
        super().__init__(args, admin_key=secrets.token_bytes(), **extra)
        self._base_dir = base_dir
        self._layout = layout
        self._colon = colon

    @property
    def backend_capability(self) -> BackendCapability:
        return BackendCapability(idle=True, object_id=True, multi_append=True)

    @property
    def base_dir(self) -> str:
        """The base directory for all relative paths."""
        return self._base_dir

    @property
    def layout(self) -> str:
        """The Maildir directory layout name.

        See Also:
            :class:`~pymap.backend.maildir.layout.MaildirLayout`

        """
        return self._layout

    @property
    def colon(self) -> str | None:
        """The info delimiter in mail filename.

        See Also:
            Note on ``colon`` in :class:`mailbox.Maildir`.

        """
        return self._colon

    @classmethod
    def parse_args(cls, args: Namespace) -> Mapping[str, Any]:
        executor = ThreadPoolExecutor(args.concurrency)
        subsystem = Subsystem.for_executor(executor)
        return {**super().parse_args(args),
                'base_dir': args.base_dir,
                'layout': args.layout,
                'colon': args.colon,
                'subsystem': subsystem}


class FilterSet(PluginFilterSet[bytes], SingleFilterSet[bytes]):

    def __init__(self, user_dir: str) -> None:
        super().__init__('sieve', bytes)
        self._user_dir = user_dir

    async def replace_active(self, value: bytes | None) -> None:
        path = os.path.join(self._user_dir, 'dovecot.sieve')
        if value is None:
            try:
                os.unlink(path)
            except FileNotFoundError:
                pass
        else:
            with open(path, 'wb') as sieve_file:
                sieve_file.write(value)

    async def get_active(self) -> bytes | None:
        path = os.path.join(self._user_dir, 'dovecot.sieve')
        try:
            with open(path, 'rb') as sieve_file:
                return sieve_file.read()
        except FileNotFoundError:
            return None


class Session(BaseSession[Message]):
    """The session implementation for the maildir backend."""

    resource = __name__

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
    """The login implementation for the maildir backend."""

    def __init__(self, config: Config) -> None:
        super().__init__()
        self.config = config
        self._passwords = Passwords(config)
        self._tokens = AllTokens(config)

    @property
    def tokens(self) -> AllTokens:
        return self._tokens

    async def authenticate(self, credentials: ServerCredentials) \
            -> Identity:
        config = self.config
        authcid = credentials.authcid
        roles: set[str] = set()
        token_id: str | None = None
        if isinstance(credentials, TokenCredentials):
            token_id = credentials.identifier
            roles.update(credentials.roles)
        identity = Identity(config, self.tokens, authcid, token_id, roles)
        try:
            user = await identity.get()
        except UserNotFound:
            await asyncio.sleep(self.config.invalid_user_sleep)
            user = UserMetadata(config, authcid)
        roles |= user.roles
        if not await self._passwords.check_password(user, credentials):
            raise InvalidAuth()
        return identity

    async def authorize(self, authenticated: IdentityInterface, authzid: str) \
            -> Identity:
        authcid = authenticated.name
        roles = authenticated.roles
        if authcid != authzid and roles.isdisjoint({'sudo', 'admin'}):
            raise AuthorizationFailure()
        return Identity(self.config, self.tokens, authzid, None, roles)


class Identity(IdentityInterface):
    """The identity implementation for the maildir backend."""

    def __init__(self, config: Config, tokens: TokensInterface,
                 name: str, token_id: str | None, roles: Set[str]) -> None:
        super().__init__()
        self.config: Final = config
        self.tokens: Final = tokens
        self._name = name
        self._token_id = token_id
        self._roles = frozenset(roles)
        self._base_dir = config.base_dir

    @property
    def name(self) -> str:
        return self._name

    @property
    def roles(self) -> frozenset[str]:
        return self._roles

    async def new_token(self, *, expiration: datetime | None = None) \
            -> str | None:
        base_dir = self._base_dir
        name = self.name
        identifier = uuid.uuid4().hex
        key = secrets.token_bytes()
        async with UsersFile.with_write(base_dir) as users_file, \
                TokensFile.with_write(base_dir) as tokens_file:
            if not users_file.has(name):
                raise UserNotFound(name)
            tokens_file.set(tokens_file.build_record(
                identifier, key, name))
        return self.tokens.get_login_token(identifier, name, key)

    @asynccontextmanager
    async def new_session(self) -> AsyncIterator[Session]:
        config = self.config
        base_dir = self._base_dir
        name = self.name
        async with UsersFile.with_read(base_dir) as users_file:
            try:
                user_record = users_file.get(name)
            except KeyError as exc:
                raise UserNotFound(name) from exc
            else:
                mailbox_path = user_record.home_dir
        maildir, layout = self._load_maildir(mailbox_path)
        mailbox_set = MailboxSet(maildir, layout)
        filter_set = FilterSet(layout.path)
        yield Session(self.name, config, mailbox_set, filter_set)

    def _load_maildir(self, mailbox_path: str) \
            -> tuple[Maildir, MaildirLayout[Any]]:
        full_path = os.path.join(self._base_dir, mailbox_path)
        layout = MaildirLayout.get(full_path, self.config.layout, Maildir)
        create = not os.path.exists(full_path)
        maildir = Maildir(full_path, create=create)
        colon = self.config.colon
        if colon is not None:
            maildir.colon = colon
        return maildir, layout

    async def get(self) -> UserMetadata:
        base_dir = self._base_dir
        name = self.name
        token_id = self._token_id
        password: str | None = None
        token_key: bytes | None = None
        roles = set(self._roles)
        async with UsersFile.with_read(base_dir) as users_file, \
                GroupsFile.with_read(base_dir) as groups_file:
            if token_id is None:
                async with PasswordsFile.with_read(base_dir) as passwords_file:
                    try:
                        password_record = passwords_file.get(name)
                    except KeyError:
                        pass
                    else:
                        password = password_record.password
                        if not password or password[0] in ('*', '!'):
                            password = None  # disabled
            else:
                async with TokensFile.with_read(base_dir) as tokens_file:
                    try:
                        token = tokens_file.get(token_id)
                    except KeyError as exc:
                        raise UserNotFound() from exc
                    else:
                        self._name = name = token.users_list
                        token_key = bytes.fromhex(token.password)
            try:
                user_record = users_file.get(name)
            except KeyError as exc:
                raise UserNotFound(name) from exc
            else:
                if user_record.uid == '0':
                    roles.add('admin')
                mailbox_path = user_record.home_dir
            for role in groups_file.get_user(name):
                roles.add(role.name)
        params = frozendict({'mailbox_path': mailbox_path})
        return UserMetadata(self.config, name, password, token_key,
                            frozenset(roles), params)

    async def set(self, metadata: UserMetadata) -> None:
        base_dir = self._base_dir
        name = self.name
        password = metadata.password if metadata.password is not None else '*'
        mailbox_path = metadata.params.get('mailbox_path', name)
        roles = metadata.roles
        if self.roles.isdisjoint({'sudo', 'admin'}):
            async with UsersFile.with_read(base_dir) as users_file, \
                    GroupsFile.with_read(base_dir) as groups_file:
                try:
                    existing_user = users_file.get(name)
                except KeyError:
                    pass
                else:
                    if mailbox_path != existing_user.home_dir:
                        raise NotAllowedError('Cannot assign parameters.')
                existing_roles = {group.name for group in
                                  groups_file.get_user(name)}
                if metadata.roles != existing_roles:
                    raise NotAllowedError('Cannot assign roles.')
        async with UsersFile.with_write(base_dir) as users_file, \
                PasswordsFile.with_write(base_dir) as passwords_file, \
                GroupsFile.with_write(base_dir) as groups_file:
            users_file.set(users_file.build_record(name, mailbox_path))
            passwords_file.set(passwords_file.build_record(name, password))
            groups_file.remove_user(name)
            groups_file.merge(groups_file.build_record(role, name)
                              for role in roles)

    async def delete(self) -> None:
        base_dir = self._base_dir
        name = self.name
        async with UsersFile.with_write(base_dir) as users_file, \
                PasswordsFile.with_write(base_dir) as passwords_file, \
                TokensFile.with_write(base_dir) as tokens_file, \
                GroupsFile.with_write(base_dir) as groups_file:
            try:
                users_file.remove(name)
            except KeyError as exc:
                raise UserNotFound(name) from exc
            try:
                passwords_file.remove(name)
            except KeyError:
                pass
            tokens_file.remove_user(name)
            groups_file.remove_user(name)
