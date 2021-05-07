
from __future__ import annotations

import os.path
from argparse import ArgumentParser, Namespace
from collections.abc import Mapping, AsyncIterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager, AsyncExitStack
from datetime import datetime
from typing import Any, Optional, Final

from pysasl.creds import AuthenticationCredentials

from pymap.concurrent import Subsystem
from pymap.config import BackendCapability, IMAPConfig
from pymap.exceptions import AuthorizationFailure, NotSupportedError
from pymap.filter import PluginFilterSet, SingleFilterSet
from pymap.health import HealthStatus
from pymap.interfaces.backend import BackendInterface
from pymap.interfaces.login import LoginInterface, IdentityInterface
from pymap.token import AllTokens
from pymap.user import UserMetadata

from .layout import MaildirLayout
from .mailbox import Message, Maildir, MailboxSet
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
        self._status = HealthStatus(True)

    @property
    def login(self) -> Login:
        return self._login

    @property
    def users(self) -> None:
        return None

    @property
    def config(self) -> Config:
        return self._config

    @property
    def status(self) -> HealthStatus:
        return self._status

    @classmethod
    def add_subparser(cls, name: str, subparsers: Any) -> ArgumentParser:
        parser = subparsers.add_parser(name, help='on-disk backend')
        parser.add_argument('users_file', help='path the the users file')
        parser.add_argument('--base-dir', metavar='DIR',
                            help='base directory for mailbox relative paths')
        parser.add_argument('--concurrency', metavar='NUM', type=int,
                            help='maximum number of IO workers')
        parser.add_argument('--layout', metavar='TYPE', default='++',
                            help='maildir directory layout')
        return parser

    @classmethod
    async def init(cls, args: Namespace, **overrides: Any) \
            -> tuple[MaildirBackend, Config]:
        config = Config.from_args(args)
        login = Login(config)
        return cls(login, config), config

    async def start(self, stack: AsyncExitStack) -> None:
        pass


class Config(IMAPConfig):
    """The config implementation for the maildir backend.

    Args:
        args: The command-line arguments.
        users_file: The path to the users file.
        base_dir: The base directory for all relative mailbox paths.
        layout: The Maildir directory layout.

    """

    def __init__(self, args: Namespace, *, users_file: str,
                 base_dir: Optional[str], layout: str, **extra: Any) -> None:
        super().__init__(args, **extra)
        self._users_file = users_file
        self._base_dir = self._get_base_dir(base_dir, users_file)
        self._layout = layout

    @classmethod
    def _get_base_dir(cls, base_dir: Optional[str],
                      users_file: Optional[str]) -> str:
        if base_dir:
            return base_dir
        elif users_file:
            return os.path.dirname(users_file)
        else:
            raise ValueError('--base-dir', base_dir)

    @property
    def backend_capability(self) -> BackendCapability:
        return BackendCapability(idle=True, object_id=True, multi_append=True)

    @property
    def users_file(self) -> str:
        """Used by the default :meth:`~Session.find_user` implementation
        to retrieve the users file path from the command-line arguments. The
        users file is given as the first positional argument on the
        command-line.

        This file contains a valid login on each line, which are split into
        three parts by colon (``:``) characters: the user name, the mailbox
        path, and the password.

        The password may contain colon characters. The mailbox path may be
        empty, relative, or absolute. If it is empty, the user ID is used as a
        relative path.

        """
        return self._users_file

    @property
    def base_dir(self) -> str:
        """The base directory for all relative mailbox paths. The default is
        the directory containing the users file.

        """
        return self._base_dir

    @property
    def layout(self) -> str:
        """The Maildir directory layout name.

        See Also:
            :class:`~pymap.backend.maildir.layout.MaildirLayout`

        """
        return self._layout

    @classmethod
    def parse_args(cls, args: Namespace) -> Mapping[str, Any]:
        executor = ThreadPoolExecutor(args.concurrency)
        subsystem = Subsystem.for_executor(executor)
        return {**super().parse_args(args),
                'users_file': args.users_file,
                'base_dir': args.base_dir,
                'layout': args.layout,
                'subsystem': subsystem}


class FilterSet(PluginFilterSet[bytes], SingleFilterSet[bytes]):

    def __init__(self, user_dir: str) -> None:
        super().__init__('sieve', bytes)
        self._user_dir = user_dir

    async def replace_active(self, value: Optional[bytes]) -> None:
        path = os.path.join(self._user_dir, 'dovecot.sieve')
        if value is None:
            try:
                os.unlink(path)
            except FileNotFoundError:
                pass
        else:
            with open(path, 'wb') as sieve_file:
                sieve_file.write(value)

    async def get_active(self) -> Optional[bytes]:
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
        self._tokens = AllTokens()

    @property
    def tokens(self) -> AllTokens:
        return self._tokens

    async def authenticate(self, credentials: AuthenticationCredentials) \
            -> Identity:
        authcid = credentials.authcid
        identity = credentials.identity
        password: Optional[str] = None
        mailbox_path: Optional[str] = None
        with open(self.config.users_file, 'r') as users_file:
            for line in users_file:
                this_user, this_user_dir, this_password = line.split(':', 2)
                if authcid == this_user:
                    password = this_password.rstrip('\r\n')
                if identity == this_user:
                    mailbox_path = this_user_dir or this_user
        data = UserMetadata(self.config, password=password)
        await data.check_password(credentials)
        if mailbox_path is None or authcid != identity:
            raise AuthorizationFailure()
        return Identity(self.config, identity, data, mailbox_path)


class Identity(IdentityInterface):
    """The identity implementation for the maildir backend."""

    def __init__(self, config: Config, name: str, metadata: UserMetadata,
                 mailbox_path: str) -> None:
        super().__init__()
        self.config: Final = config
        self.metadata: Final = metadata
        self.mailbox_path: Final = mailbox_path
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    async def new_token(self, *, expiration: datetime = None) -> None:
        return None

    @asynccontextmanager
    async def new_session(self) -> AsyncIterator[Session]:
        config = self.config
        maildir, layout = self._load_maildir()
        mailbox_set = MailboxSet(maildir, layout)
        filter_set = FilterSet(layout.path)
        yield Session(self.name, config, mailbox_set, filter_set)

    def _load_maildir(self) -> tuple[Maildir, MaildirLayout]:
        full_path = os.path.join(self.config.base_dir, self.mailbox_path)
        layout = MaildirLayout.get(full_path, self.config.layout, Maildir)
        create = not os.path.exists(full_path)
        return Maildir(full_path, create=create), layout

    async def get(self) -> UserMetadata:
        return self.metadata

    async def set(self, metadata: UserMetadata) -> None:
        raise NotSupportedError()

    async def delete(self) -> None:
        raise NotSupportedError()
