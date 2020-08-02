
from __future__ import annotations

import asyncio
import os.path
from argparse import ArgumentParser, Namespace
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from typing import Any, Optional, Tuple, Sequence, Mapping, Awaitable, \
    AsyncIterator

from pysasl import AuthenticationCredentials

from pymap.concurrent import Subsystem
from pymap.config import BackendCapability, IMAPConfig
from pymap.exceptions import InvalidAuth
from pymap.filter import PluginFilterSet, SingleFilterSet
from pymap.interfaces.backend import BackendInterface, ServiceInterface
from pymap.interfaces.session import LoginProtocol

from .layout import MaildirLayout
from .mailbox import Message, Maildir, MailboxSet
from ..session import BaseSession

__all__ = ['MaildirBackend', 'Config', 'Session']


class MaildirBackend(BackendInterface):
    """Defines an on-disk backend that uses :class:`~mailbox.Maildir` for
    mailbox storage and `MailboxFormat/Maildir
    <https://wiki2.dovecot.org/MailboxFormat/Maildir>`_ for metadata storage.

    """

    def __init__(self, login: Login, config: Config) -> None:
        super().__init__()
        self._login = login
        self._config = config

    @property
    def login(self) -> Login:
        return self._login

    @property
    def users(self) -> None:
        return None

    @property
    def config(self) -> Config:
        return self._config

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
    async def init(cls, args: Namespace) -> Tuple[MaildirBackend, Config]:
        config = Config.from_args(args)
        login = Login(config)
        return cls(login, config), config

    async def start(self, services: Sequence[ServiceInterface]) -> Awaitable:
        tasks = [await service.start() for service in services]
        return asyncio.gather(*tasks)


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


class Login(LoginProtocol):
    """The login implementation for the maildir backend."""

    def __init__(self, config: Config) -> None:
        super().__init__()
        self.config = config

    @asynccontextmanager
    async def __call__(self, credentials: AuthenticationCredentials) \
            -> AsyncIterator[Session]:
        """Checks the given credentials for a valid login and returns a new
        session.

        """
        user = credentials.authcid
        config = self.config
        password, user_dir = await self.find_user(user)
        if user != credentials.identity:
            raise InvalidAuth()
        elif not credentials.check_secret(password):
            raise InvalidAuth()
        maildir, layout = self._load_maildir(user_dir)
        mailbox_set = MailboxSet(maildir, layout)
        filter_set = FilterSet(layout.path)
        yield Session(credentials.identity, config, mailbox_set, filter_set)

    async def find_user(self, user: str) -> Tuple[str, str]:
        """If the given user ID exists, return its expected password and
        mailbox path. Override this method to implement custom login logic.

        Args:
            config: The maildir config object.
            user: The expected user ID.

        Raises:
            InvalidAuth: The user ID was not valid.

        """
        with open(self.config.users_file, 'r') as users_file:
            for line in users_file:
                this_user, user_dir, password = line.split(':', 2)
                if user == this_user:
                    return password.rstrip('\r\n'), user_dir or user
        raise InvalidAuth()

    def _load_maildir(self, user_dir: str) \
            -> Tuple[Maildir, MaildirLayout]:
        full_path = os.path.join(self.config.base_dir, user_dir)
        layout = MaildirLayout.get(full_path, self.config.layout, Maildir)
        create = not os.path.exists(full_path)
        return Maildir(full_path, create=create), layout
