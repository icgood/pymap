
import uuid
from argparse import Namespace, ArgumentDefaultsHelpFormatter
from typing import Any, Mapping

from aioredis import create_redis, Redis  # type: ignore
from pysasl import AuthenticationCredentials

from pymap.config import IMAPConfig
from pymap.exceptions import InvalidAuth, MailboxConflict
from pymap.interfaces.backend import BackendInterface
from pymap.server import IMAPServer

from .mailbox import Message, MailboxSet
from ..session import BaseSession

try:
    from passlib.apps import ldap_context  # type: ignore
except ImportError:
    ldap_context = None

__all__ = ['RedisBackend', 'Config', 'Session']


class RedisBackend(IMAPServer, BackendInterface):
    """Defines a backend that uses redis data structures for mailbox storage.

    """

    @classmethod
    def add_subparser(cls, subparsers) -> None:
        parser = subparsers.add_parser(
            'redis', help='redis backend',
            formatter_class=ArgumentDefaultsHelpFormatter)
        parser.add_argument('address', default='redis://localhost', nargs='?',
                            help='the redis server address')

    @classmethod
    async def init(cls, args: Namespace) -> 'RedisBackend':
        return cls(Session.login, Config.from_args(args))


class Config(IMAPConfig):
    """The config implementation for the redis backend.

    Args:
        args: The command-line arguments.
        address: The redis server address.

    """

    def __init__(self, args: Namespace, address: str, **extra: Any) -> None:
        super().__init__(args, **extra)
        self._address = address

    @property
    def address(self) -> str:
        """The redis server address."""
        return self._address

    @classmethod
    def parse_args(cls, args: Namespace, **extra: Any) -> Mapping[str, Any]:
        return super().parse_args(args, address=args.address, **extra)


class Session(BaseSession[Message]):
    """The session implementation for the redis backend."""

    resource = __name__

    def __init__(self, config: Config, mailbox_set: MailboxSet) -> None:
        super().__init__()
        self._config = config
        self._mailbox_set = mailbox_set

    @property
    def config(self) -> IMAPConfig:
        return self._config

    @property
    def mailbox_set(self) -> MailboxSet:
        return self._mailbox_set

    @classmethod
    async def login(cls, credentials: AuthenticationCredentials,
                    config: Config) -> 'Session':
        """Checks the given credentials for a valid login and returns a new
        session.

        """
        redis = await create_redis(config.address)
        prefix = await cls._check_user(redis, config, credentials)
        mailbox_set = MailboxSet(redis, prefix)
        try:
            await mailbox_set.add_mailbox('INBOX')
        except MailboxConflict:
            pass
        return cls(config, mailbox_set)

    @classmethod
    async def _check_user(cls, redis: Redis, config: IMAPConfig,
                          credentials: AuthenticationCredentials) -> bytes:
        user = credentials.authcid
        multi = redis.multi_exec()
        multi.hget(b'_users', user)
        multi.hsetnx(b'_prefixes', user, uuid.uuid4().hex)
        multi.hget(b'_prefixes', user)
        password, _, prefix = await multi.execute()
        if password is None:
            raise InvalidAuth()
        elif ldap_context is None or not credentials.has_secret:
            if not credentials.check_secret(password):
                raise InvalidAuth()
        elif not ldap_context.verify(credentials.secret, password):
            raise InvalidAuth()
        return prefix
