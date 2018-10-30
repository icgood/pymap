"""Defines a demo configuration that uses an in-memory dictionary for
example usage and integration testing.

"""

import os.path
from argparse import Namespace
from contextlib import closing
from datetime import datetime, timezone
from typing import Any, Tuple, Mapping, Dict

from pkg_resources import resource_listdir, resource_stream
from pysasl import AuthenticationCredentials

from pymap.config import IMAPConfig
from pymap.exceptions import InvalidAuth
from pymap.interfaces.session import LoginProtocol
from pymap.parsing.specials import Flag

from .mailbox import Message, Mailbox
from ..session import Session

__all__ = ['add_subparser', 'init']


def add_subparser(subparsers) -> None:
    demo = subparsers.add_parser('demo', help='in-memory demo backend')
    demo.add_argument('-d', '--demo-data', action='store_true',
                      help='load initial demo data')


async def init(args: Namespace) -> Tuple[LoginProtocol, '_Config']:
    return _Session.login, _Config.from_args(args)


class _Config(IMAPConfig):

    credentials = {'demouser': 'demopass'}

    def __init__(self, demo_data: bool, **extra: Any) -> None:
        super().__init__(**extra)
        self.demo_data = demo_data
        self.inbox_cache: Dict[str, Mailbox] = {}

    @classmethod
    def parse_args(cls, args: Namespace, **extra: Any) -> Mapping[str, Any]:
        return super().parse_args(args, demo_data=args.demo_data, **extra)


class _Session(Session[Mailbox, Message]):

    resource = __name__

    @classmethod
    async def login(cls, credentials: AuthenticationCredentials,
                    config: _Config) -> '_Session':
        user = credentials.authcid
        password = config.credentials.get(user)
        if not password or not credentials.check_secret(password):
            raise InvalidAuth()
        inbox = config.inbox_cache.get(user)
        if not inbox:
            inbox = Mailbox('INBOX')
            if config.demo_data:
                await cls._load_demo(inbox)
            config.inbox_cache[user] = inbox
        return cls(inbox, Message)

    @classmethod
    async def _load_demo(cls, inbox: Mailbox) -> None:
        await cls._load_demo_mailbox('INBOX', inbox)
        mbx_names = sorted(resource_listdir(cls.resource, 'data'))
        for name in mbx_names:
            if name != 'INBOX':
                mailbox = await inbox.add_mailbox(name)
                await cls._load_demo_mailbox(name, mailbox)

    @classmethod
    async def _load_demo_mailbox(cls, name: str, mailbox: Mailbox) -> None:
        path = os.path.join('data', name)
        msg_names = sorted(resource_listdir(cls.resource, path))
        for msg_name in msg_names:
            if msg_name == '.ignore':
                continue
            msg_path = os.path.join(path, msg_name)
            message_stream = resource_stream(cls.resource, msg_path)
            with closing(message_stream):
                flags_line = message_stream.readline()
                msg_timestamp = float(message_stream.readline())
                msg_dt = datetime.fromtimestamp(msg_timestamp, timezone.utc)
                msg_flags = {Flag(flag) for flag in flags_line.split()}
                msg_data = message_stream.read()
            msg = Message.parse(0, msg_data, msg_flags, msg_dt)
            await mailbox.add(msg)
