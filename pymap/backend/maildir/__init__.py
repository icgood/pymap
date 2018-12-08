
import os.path
from argparse import Namespace
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Optional, Tuple, Mapping, TypeVar, Type

from pysasl import AuthenticationCredentials

from pymap.config import IMAPConfig
from pymap.exceptions import InvalidAuth
from pymap.interfaces.backend import BackendInterface
from pymap.server import IMAPServer

from .layout import MaildirLayout
from .mailbox import Message, Maildir, MailboxSet
from ..session import BaseSession

__all__ = ['MaildirBackend', 'Config', 'Session']

_SessionT = TypeVar('_SessionT', bound='Session')


class MaildirBackend(IMAPServer, BackendInterface):
    """Defines an on-disk backend that uses :class:`~mailbox.Maildir` for
    mailbox storage and `MailboxFormat/Maildir
    <https://wiki2.dovecot.org/MailboxFormat/Maildir>`_ for metadata storage.

    """

    @classmethod
    def add_subparser(cls, subparsers) -> None:
        parser = subparsers.add_parser('maildir', help='on-disk backend')
        parser.add_argument('users_file', metavar='PATH',
                            help='Path the the users file.')
        parser.add_argument('-d', '--base-dir', metavar='DIR',
                            help='Base directory for mailbox relative paths.')
        parser.add_argument('-t', '--concurrency', metavar='NUM', type=int,
                            help='Maximum number of IO workers.')
        parser.add_argument('-l', '--layout', metavar='TYPE',
                            help='Maildir directory layout.')

    @classmethod
    async def init(cls, args: Namespace) -> 'MaildirBackend':
        return cls(Session.login, Config.from_args(args))


class Config(IMAPConfig):
    """The config implementation for the maildir backend.

    Args:
        args: The command-line arguments.
        users_file: The path to the users file, see :attr:`.users_file`.
        base_dir: The base directory for all relative mailbox paths.
        layout: The Maildir directory layout.

    """

    def __init__(self, args: Namespace, users_file: str = None,
                 base_dir: str = None, layout: str = '++',
                 **extra: Any) -> None:
        super().__init__(args, **extra)
        self._users_file = users_file
        self.base_dir = self._get_base_dir(base_dir, users_file)
        self.layout = layout

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
        if not self._users_file:
            raise ValueError('users_file', self._users_file)
        return self._users_file

    @classmethod
    def parse_args(cls, args: Namespace, **extra: Any) -> Mapping[str, Any]:
        executor = ThreadPoolExecutor(args.concurrency)
        return super().parse_args(args, users_file=args.users_file,
                                  base_dir=args.base_dir,
                                  layout=args.layout,
                                  executor=executor, **extra)


class Session(BaseSession[Message]):
    """The session implementation for the maildir backend."""

    resource = __name__

    def __init__(self, mailbox_set: MailboxSet) -> None:
        super().__init__()
        self._mailbox_set = mailbox_set

    @property
    def mailbox_set(self) -> MailboxSet:
        return self._mailbox_set

    @classmethod
    async def login(cls: Type[_SessionT],
                    credentials: AuthenticationCredentials,
                    config: Config) -> _SessionT:
        """Checks the given credentials for a valid login and returns a new
        session.

        """
        user = credentials.authcid
        password, user_dir = await cls.find_user(config, user)
        if not credentials.check_secret(password):
            raise InvalidAuth()
        maildir, layout = cls._load_maildir(config, user_dir)
        mailbox_set = MailboxSet(maildir, layout)
        return cls(mailbox_set)

    @classmethod
    async def find_user(cls, config: Config, user: str) \
            -> Tuple[str, str]:
        """If the given user ID exists, return its expected password and
        mailbox path. Override this method to implement custom login logic.

        Args:
            config: The maildir config object.
            user: The expected user ID.

        Raises:
            InvalidAuth: The user ID was not valid.

        """
        with open(config.users_file, 'r') as users_file:
            for line in users_file:
                this_user, user_dir, password = line.split(':', 2)
                if user == this_user:
                    return password.rstrip('\r\n'), user_dir or user
        raise InvalidAuth()

    @classmethod
    def _load_maildir(cls, config: Config, user_dir: str) \
            -> Tuple[Maildir, MaildirLayout]:
        full_path = os.path.join(config.base_dir, user_dir)
        layout = MaildirLayout.get(full_path, config.layout, Maildir)
        return Maildir(full_path, create=True), layout
