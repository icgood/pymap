"""Defines an on-disk configuration that uses :class:`~mailbox.Maildir` for
mailbox storage and :mod:`dbm` for metadata storage.

"""

import os.path
from argparse import Namespace
from concurrent.futures import ThreadPoolExecutor
from mailbox import Maildir  # type: ignore
from typing import Any, Tuple, Mapping, Dict

from pysasl import AuthenticationCredentials

from pymap.config import IMAPConfig
from pymap.exceptions import InvalidAuth
from pymap.interfaces.session import LoginProtocol

from .mailbox import Message, Mailbox
from ..session import Session

__all__ = ['add_subparser', 'init']


def add_subparser(subparsers) -> None:
    parser = subparsers.add_parser('maildir', help='on-disk backend')
    parser.add_argument('users_file', metavar='PATH',
                        help='Path the the users file.')
    parser.add_argument('-d', '--base-dir', metavar='DIR',
                        help='Base directory for mailbox relative paths.')
    parser.add_argument('-t', '--concurrency', metavar='NUM', type=int,
                        help='Maximum number of IO workers.')


async def init(args: Namespace) -> Tuple[LoginProtocol, '_Config']:
    return _Session.login, _Config.from_args(args)


class _Config(IMAPConfig):

    def __init__(self, users_file: str, base_dir: str = None,
                 **extra: Any) -> None:
        super().__init__(**extra)
        self.users_file = users_file
        self.base_dir = base_dir or ''
        self.inbox_cache: Dict[str, Mailbox] = {}

    @classmethod
    def parse_args(cls, args: Namespace, **extra: Any) -> Mapping[str, Any]:
        executor = ThreadPoolExecutor(args.concurrency)
        return super().parse_args(args, users_file=args.users_file,
                                  base_dir=args.base_dir,
                                  executor=executor, **extra)


class _Session(Session[Mailbox, Message]):

    resource = __name__

    @classmethod
    async def login(cls, credentials: AuthenticationCredentials,
                    config: _Config) -> '_Session':
        user = credentials.authcid
        password, user_dir = cls._find_user(config, user)
        if not credentials.check_secret(password):
            raise InvalidAuth()
        inbox = config.inbox_cache.get(user)
        if not inbox:
            maildir = cls._load_maildir(config, user_dir)
            inbox = Mailbox('INBOX', maildir)
            config.inbox_cache[user] = inbox
        return cls(inbox, Message)

    @classmethod
    def _find_user(cls, config: _Config, user: str) -> Tuple[str, str]:
        with open(config.users_file, 'r') as users_file:
            for line in users_file:
                this_user, user_dir, password = line.split(':', 2)
                if user == this_user:
                    return password.rstrip('\r\n'), user_dir or user
        raise InvalidAuth()

    @classmethod
    def _load_maildir(cls, config: _Config, user_dir: str) -> Maildir:
        full_path = os.path.join(config.base_dir, user_dir)
        return Maildir(full_path, create=True)
