import os.path
import ssl
from argparse import Namespace
from concurrent.futures import Executor
from ssl import SSLContext
from typing import Sequence, Any, Optional, Mapping, TypeVar, Type, Callable

from pysasl import SASLAuth, AuthenticationCredentials

from .concurrent import Event, ReadWriteLock
from .parsing import Params
from .parsing.commands import Commands

__all__ = ['IMAPConfig', 'ConfigT', 'ConfigT_contra']

#: Type variable with an upper bound of :class:`IMAPConfig`.
ConfigT = TypeVar('ConfigT', bound='IMAPConfig')

#: Contravariant type variable with an upper bound of :class:`IMAPConfig`.
ConfigT_contra = TypeVar('ConfigT_contra', bound='IMAPConfig',
                         contravariant=True)


class IMAPConfig:
    """Configurable settings that control how the IMAP server operates and what
    extensions it supports.

    Args:
        args: The command-line arguments.
        debug: If true, prints all socket activity to stdout.
        executor: If given, all backend operations will be run inside this
            executor object, e.g. a thread pool.
        ssl_context: SSL context that will be used for opportunistic TLS.
            Alternatively, you can pass extra arguments ``cert_file`` and
            ``key_file`` and an SSL context will be created.
        starttls_enabled: True if opportunistic TLS should be supported.
        reject_insecure_auth: True if authentication mechanisms that transmit
            credentials in cleartext should be rejected on non-encrypted
            transports.
        preauth_credentials: If given, clients will pre-authenticate on
            connection using these credentials.
        max_append_len: The maximum allowed length of the message body to an
            ``APPEND`` command.
        bad_command_limit: The number of consecutive commands received from
            the client with parsing errors before the client is disconnected.
        disable_idle: Disable the ``IDLE`` capability.
        extra: Additional keywords used for special circumstances.

    Attributes:
        args: The command-line arguments.

    """

    def __init__(self, args: Namespace,
                 debug: bool = False,
                 executor: Executor = None,
                 ssl_context: SSLContext = None,
                 starttls_enabled: bool = True,
                 reject_insecure_auth: bool = True,
                 preauth_credentials: AuthenticationCredentials = None,
                 max_append_len: Optional[int] = 1000000000,
                 bad_command_limit: Optional[int] = 5,
                 disable_idle: bool = False,
                 **extra: Any) -> None:
        super().__init__()
        self.args = args
        self._debug = debug
        self._executor = executor
        self._ssl_context = ssl_context
        self._starttls_enabled = starttls_enabled
        self._reject_insecure_auth = reject_insecure_auth
        self._preauth_credentials = preauth_credentials
        self._max_append_len = max_append_len
        self._bad_command_limit = bad_command_limit
        self._disable_idle = disable_idle
        self._extra = extra

    @classmethod
    def parse_args(cls, args: Namespace, **extra: Any) -> Mapping[str, Any]:
        """Given command-line arguments, return a dictionary of keywords that
        should be passed in to the :class:`IMAPConfig` (or sub-class)
        constructor. Sub-classes should override this method as needed.

        Args:
            args: The arguments parsed from the command-line.
            extra: Additional keywords used by sub-classes.

        """
        ret = {'debug': args.debug,
               'reject_insecure_auth': not args.insecure_login}
        for key, val in extra.items():
            if val is not None:
                ret[key] = val
        return ret

    @classmethod
    def from_args(cls: Type[ConfigT], args: Namespace,
                  **extra: Any) -> ConfigT:
        """Build and return a new :class:`IMAPConfig` using command-line
        arguments.

        Args:
            args: The arguments parsed from the command-line.
            extra: Additional keywords used by sub-classes.

        """
        params = cls.parse_args(args, **extra)
        return cls(args, **params)

    @property
    def debug(self) -> bool:
        return self._debug

    @property
    def executor(self) -> Optional[Executor]:
        return self._executor

    @property
    def new_rwlock(self) -> Callable[[], ReadWriteLock]:
        if self._executor is None:
            return ReadWriteLock.for_asyncio
        else:
            return ReadWriteLock.for_threading

    @property
    def new_event(self) -> Callable[[], Event]:
        if self._executor is None:
            return Event.for_asyncio
        else:
            return Event.for_threading

    @property
    def bad_command_limit(self) -> Optional[int]:
        return self._bad_command_limit

    @property
    def ssl_context(self) -> Optional[SSLContext]:
        if self._ssl_context is None:
            cert_file: Optional[str] = getattr(self.args, 'cert', None)
            if cert_file is None:
                return None
            key_file: str = getattr(self.args, 'key', cert_file)
            cert_path = os.path.realpath(cert_file)
            key_path = os.path.realpath(key_file)
            ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            ssl_context.load_cert_chain(cert_path, key_path)
            self._ssl_context = ssl_context
        return self._ssl_context

    @property
    def commands(self) -> Commands:
        return Commands()

    @property
    def initial_auth(self) -> SASLAuth:
        if self._reject_insecure_auth:
            return SASLAuth.secure()
        else:
            return SASLAuth()

    @property
    def starttls_auth(self) -> SASLAuth:
        return SASLAuth()

    @property
    def preauth_credentials(self) -> Optional[AuthenticationCredentials]:
        return self._preauth_credentials

    @property
    def parsing_params(self) -> Params:
        return Params(max_append_len=self._max_append_len)

    @property
    def login_capability(self) -> Sequence[bytes]:
        ret = [b'BINARY', b'UIDPLUS', b'MULTIAPPEND', b'CHILDREN']
        if not self._disable_idle:
            ret.append(b'IDLE')
        if self._max_append_len is not None:
            ret.append(b'APPENDLIMIT=%i' % self._max_append_len)
        return ret

    @property
    def initial_capability(self) -> Sequence[bytes]:
        ret = []
        if self._starttls_enabled:
            ret.append(b'STARTTLS')
        if self._reject_insecure_auth:
            ret.append(b'LOGINDISABLED')
        return ret
