"""Defines a configuration that uses an in-memory dictionary for example usage
and integration testing.

"""

import os.path
from argparse import Namespace
from contextlib import closing
from datetime import datetime, timezone
from typing import Any, Tuple, Mapping, Dict, TypeVar, Type

from pkg_resources import resource_listdir, resource_stream
from pysasl import AuthenticationCredentials

from pymap.config import IMAPConfig
from pymap.exceptions import InvalidAuth
from pymap.interfaces.session import LoginProtocol
from pymap.parsing.specials.flag import Flag, Recent
from pymap.sockinfo import SocketInfo

from .mailbox import Message, Mailbox
from ..session import KeyValSession

__all__ = ['add_subparser', 'init', 'Config', 'Session', 'Message', 'Mailbox']

_SessionT = TypeVar('_SessionT', bound='Session')


def add_subparser(subparsers) -> None:
    parser = subparsers.add_parser('dict', help='in-memory backend')
    parser.add_argument('-d', '--demo-data', action='store_true',
                        help='load initial demo data')
    parser.add_argument('-u', '--demo-user', default='demouser',
                        help='demo user ID [%default]')
    parser.add_argument('-p', '--demo-password', default='demopass',
                        help='demo user password [%default]')


async def init(args: Namespace) -> Tuple[LoginProtocol, 'Config']:
    return Session.login, Config.from_args(args)


class Config(IMAPConfig):
    """The config implementation for the dict backend.

    Args:
        args: The command-line arguments.
        demo_data: Load the demo data, used by integration tests.

    """

    def __init__(self, args: Namespace, demo_data: bool, **extra: Any) -> None:
        super().__init__(args, **extra)
        self.demo_data = demo_data
        self.inbox_cache: Dict[str, Mailbox] = {}

    @property
    def demo_user(self) -> str:
        """Used by the default :meth:`~Session.get_password` implementation
        to retrieve the ``--demo-user`` command-line argument, which defaults
        to ``demouser``.

        """
        return self.args.demo_user

    @property
    def demo_password(self) -> str:
        """Used by the default :meth:`~Session.get_password` implementation
        to retrieve the ``--demo-password`` command-line argument, which
        defaults to ``demopass``.

        """
        return self.args.demo_password

    @classmethod
    def parse_args(cls, args: Namespace, **extra: Any) -> Mapping[str, Any]:
        return super().parse_args(args, demo_data=args.demo_data, **extra)


class Session(KeyValSession):
    """The session implementation for the dict backend."""

    resource = __name__

    @classmethod
    async def login(cls: Type[_SessionT],
                    credentials: AuthenticationCredentials,
                    config: Config, sock_info: SocketInfo) -> _SessionT:
        """Checks the given credentials for a valid login and returns a new
        session. The mailbox data is shared between concurrent and future
        sessions, but only for the lifetime of the process.

        """
        _ = sock_info  # noqa
        user = credentials.authcid
        password = await cls.get_password(config, user)
        if not password or not credentials.check_secret(password):
            raise InvalidAuth()
        inbox = config.inbox_cache.get(user)
        if not inbox:
            inbox = Mailbox('INBOX')
            if config.demo_data:
                await cls._load_demo(inbox)
            config.inbox_cache[user] = inbox
        return cls(inbox, '.')

    @classmethod
    async def get_password(cls, config: Config, user: str) -> str:
        """If the given user ID exists, return its expected password. Override
        this method to implement custom login logic.

        Args:
            config: The dict config object.
            user: The expected user ID.

        Raises:
            InvalidAuth: The user ID was not valid.

        """
        expected_user: str = config.demo_user
        expected_password: str = config.demo_password
        if user == expected_user:
            return expected_password
        raise InvalidAuth()

    @classmethod
    async def _load_demo(cls, inbox: Mailbox) -> None:
        await cls._load_demo_mailbox('INBOX', inbox)
        mbx_names = sorted(resource_listdir(cls.resource, 'demo'))
        for name in mbx_names:
            if name != 'INBOX':
                mbx = await inbox.add_mailbox(name)
                await cls._load_demo_mailbox(name, mbx)

    @classmethod
    async def _load_demo_mailbox(cls, name: str, mbx: Mailbox) -> None:
        path = os.path.join('demo', name)
        msg_names = sorted(resource_listdir(cls.resource, path))
        for msg_name in msg_names:
            if msg_name == '.readonly':
                mbx._readonly = True
                continue
            elif msg_name.startswith('.'):
                continue
            msg_path = os.path.join(path, msg_name)
            message_stream = resource_stream(cls.resource, msg_path)
            with closing(message_stream):
                flags_line = message_stream.readline()
                msg_timestamp = float(message_stream.readline())
                msg_dt = datetime.fromtimestamp(msg_timestamp, timezone.utc)
                msg_flags = {Flag(flag) for flag in flags_line.split()}
                if Recent in msg_flags:
                    msg_flags.remove(Recent)
                    msg_recent = True
                else:
                    msg_recent = False
                msg_data = message_stream.read()
            msg = Message.parse(0, msg_data, msg_flags, msg_dt, msg_recent)
            await mbx.add(msg)
