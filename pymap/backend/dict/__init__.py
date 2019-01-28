
import os.path
from argparse import Namespace, ArgumentDefaultsHelpFormatter
from contextlib import closing
from datetime import datetime, timezone
from typing import Any, Optional, Tuple, Mapping, Dict

from pkg_resources import resource_listdir, resource_stream
from pysasl import AuthenticationCredentials

from pymap.config import IMAPConfig
from pymap.exceptions import InvalidAuth
from pymap.filter import EntryPointFilterSet, SingleFilterSet
from pymap.interfaces.backend import BackendInterface
from pymap.interfaces.filter import FilterInterface
from pymap.interfaces.session import LoginProtocol
from pymap.parsing.specials.flag import Flag, Recent

from .mailbox import Message, MailboxData, MailboxSet
from ..session import BaseSession

__all__ = ['DictBackend', 'Config', 'Session']


class DictBackend(BackendInterface):
    """Defines a backend that uses an in-memory dictionary for example usage
    and integration testing.

    """

    def __init__(self, login: LoginProtocol, config: IMAPConfig) -> None:
        super().__init__()
        self._login = login
        self._config = config

    @property
    def login(self) -> LoginProtocol:
        return self._login

    @property
    def config(self) -> IMAPConfig:
        return self._config

    @classmethod
    def add_subparser(cls, subparsers) -> None:
        parser = subparsers.add_parser(
            'dict', help='in-memory backend',
            formatter_class=ArgumentDefaultsHelpFormatter)
        parser.add_argument('--demo-data', action='store_true',
                            help='load initial demo data')
        parser.add_argument('--demo-user', default='demouser',
                            metavar='VAL', help='demo user ID')
        parser.add_argument('--demo-password', default='demopass',
                            metavar='VAL', help='demo user password')

    @classmethod
    async def init(cls, args: Namespace) -> 'DictBackend':
        return cls(Session.login, Config.from_args(args))


class Config(IMAPConfig):
    """The config implementation for the dict backend."""

    def __init__(self, args: Namespace, *, demo_data: bool,
                 demo_user: str, demo_password: str, **extra: Any) -> None:
        super().__init__(args, **extra)
        self._demo_data = demo_data
        self._demo_user = demo_user
        self._demo_password = demo_password
        self.set_cache: Dict[str, Tuple[MailboxSet, 'FilterSet']] = {}

    @property
    def demo_data(self) -> bool:
        """True if demo data should be loaded at startup."""
        return self._demo_data

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
        return {'demo_data': args.demo_data,
                'demo_user': args.demo_user,
                'demo_password': args.demo_password}


class FilterSet(EntryPointFilterSet[bytes], SingleFilterSet):

    def __init__(self) -> None:
        super().__init__()
        self._sieve: Optional[bytes] = None

    @property
    def entry_point(self) -> str:
        return 'sieve'

    def set_sieve(self, sieve: bytes) -> None:
        self._sieve = sieve

    async def get_active(self) -> Optional[FilterInterface]:
        if self._sieve is None:
            return None
        else:
            try:
                return self.get_filter(self._sieve)
            except LookupError:
                return None


class Session(BaseSession[Message]):
    """The session implementation for the dict backend."""

    resource = __name__

    def __init__(self, config: Config, mailbox_set: MailboxSet,
                 filter_set: FilterSet) -> None:
        super().__init__()
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

    @classmethod
    async def login(cls, credentials: AuthenticationCredentials,
                    config: Config) -> 'Session':
        """Checks the given credentials for a valid login and returns a new
        session. The mailbox data is shared between concurrent and future
        sessions, but only for the lifetime of the process.

        """
        user = credentials.authcid
        password = cls._get_password(config, user)
        if not credentials.check_secret(password):
            raise InvalidAuth()
        mailbox_set, filter_set = config.set_cache.get(user, (None, None))
        if not mailbox_set or not filter_set:
            mailbox_set = MailboxSet()
            filter_set = FilterSet()
            if config.demo_data:
                await cls._load_demo(mailbox_set, filter_set)
            config.set_cache[user] = (mailbox_set, filter_set)
        return cls(config, mailbox_set, filter_set)

    @classmethod
    def _get_password(cls, config: Config, user: str) -> str:
        expected_user: str = config.demo_user
        expected_password: str = config.demo_password
        if user == expected_user:
            return expected_password
        raise InvalidAuth()

    @classmethod
    async def _load_demo(cls, mailbox_set: MailboxSet,
                         filter_set: FilterSet) -> None:
        inbox = await mailbox_set.get_mailbox('INBOX')
        await cls._load_demo_mailbox('INBOX', inbox)
        mbx_names = sorted(resource_listdir(cls.resource, 'demo'))
        for name in mbx_names:
            if name == 'sieve':
                cls._load_demo_sieve(name, filter_set)
            elif name != 'INBOX':
                mbx = await mailbox_set.add_mailbox(name)
                await cls._load_demo_mailbox(name, mbx)

    @classmethod
    def _load_demo_sieve(cls, name: str, filter_set: FilterSet) -> None:
        path = os.path.join('demo', name)
        sieve_stream = resource_stream(cls.resource, path)
        with closing(sieve_stream):
            sieve = sieve_stream.read()
        filter_set.set_sieve(sieve)

    @classmethod
    async def _load_demo_mailbox(cls, name: str, mbx: MailboxData) -> None:
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
                msg_data = message_stream.read()
                msg_dt = datetime.fromtimestamp(msg_timestamp, timezone.utc)
                msg_flags = {Flag(flag) for flag in flags_line.split()}
                if Recent in msg_flags:
                    msg_flags.remove(Recent)
                    msg_recent = True
                else:
                    msg_recent = False
                msg = Message.parse(0, msg_data, msg_flags, msg_dt)
            await mbx.add(msg.append_msg, msg_recent)
