"""Defines an on-disk configuration that uses :class:`~mailbox.Maildir` for
mailbox storage and :mod:`dbm` for metadata storage.

"""

import os.path
from argparse import Namespace
from concurrent.futures import ThreadPoolExecutor
from mailbox import Maildir  # type: ignore
from typing import Any, Tuple, Mapping, TypeVar, Type

from pysasl import AuthenticationCredentials

from pymap.config import IMAPConfig
from pymap.exceptions import InvalidAuth
from pymap.interfaces.session import LoginProtocol

from .mailbox import MailboxSnapshot, Message, Mailbox
from ..session import KeyValSession

__all__ = ['add_subparser', 'init', 'Config', 'Session',
           'MailboxSnapshot', 'Message', 'Mailbox']

_ST = TypeVar('_ST', bound='Session')


def add_subparser(subparsers) -> None:
    parser = subparsers.add_parser('maildir', help='on-disk backend')
    parser.add_argument('users_file', metavar='PATH',
                        help='Path the the users file.')
    parser.add_argument('-d', '--base-dir', metavar='DIR', default='',
                        help='Base directory for mailbox relative paths.')
    parser.add_argument('-t', '--concurrency', metavar='NUM', type=int,
                        help='Maximum number of IO workers.')


async def init(args: Namespace) -> Tuple[LoginProtocol, IMAPConfig]:
    return Session.login, Config.from_args(args)


class Config(IMAPConfig):
    """The config implementation for the maildir backend.

    Args:
        args: The command-line arguments.
        base_dir: The base directory for all relative mailbox paths.

    """

    def __init__(self, args: Namespace, base_dir: str = None,
                 **extra: Any) -> None:
        super().__init__(args, **extra)
        self.base_dir = base_dir or ''

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
        return self.args.users_file

    @classmethod
    def parse_args(cls, args: Namespace, **extra: Any) -> Mapping[str, Any]:
        executor = ThreadPoolExecutor(args.concurrency)
        return super().parse_args(args, base_dir=args.base_dir,
                                  executor=executor, **extra)


class Session(KeyValSession[Mailbox, Message]):
    """The session implementation for the maildir backend."""

    resource = __name__

    @classmethod
    async def login(cls: Type[_ST], credentials: AuthenticationCredentials,
                    config: Config) -> _ST:
        """Checks the given credentials for a valid login and returns a new
        session.

        """
        user = credentials.authcid
        password, user_dir = await cls.find_user(config, user)
        if not credentials.check_secret(password):
            raise InvalidAuth()
        maildir = cls._load_maildir(config, user_dir)
        inbox = Mailbox('INBOX', maildir)
        return cls(inbox, Message)

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
        with open(config.args.users_file, 'r') as users_file:
            for line in users_file:
                this_user, user_dir, password = line.split(':', 2)
                if user == this_user:
                    return password.rstrip('\r\n'), user_dir or user
        raise InvalidAuth()

    @classmethod
    def _load_maildir(cls, config: Config, user_dir: str) -> Maildir:
        full_path = os.path.join(config.base_dir, user_dir)
        return Maildir(full_path, create=True)
