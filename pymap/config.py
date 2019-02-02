import os.path
import socket
import ssl
from argparse import Namespace
from ssl import SSLContext
from typing import Sequence, Any, Optional, Iterable, Mapping, TypeVar, Type
from typing_extensions import Final

from pysasl import SASLAuth, AuthenticationCredentials

from .concurrent import Subsystem
from .context import subsystem
from .parsing import Params
from .parsing.commands import Commands

__all__ = ['IMAPConfig', 'ConfigT', 'ConfigT_co', 'ConfigT_contra']

#: Type variable with an upper bound of :class:`IMAPConfig`.
ConfigT = TypeVar('ConfigT', bound='IMAPConfig')

#: Covariant type variable with an upper bound of :class:`IMAPConfig`.
ConfigT_co = TypeVar('ConfigT_co', bound='IMAPConfig', covariant=True)

#: Contravariant type variable with an upper bound of :class:`IMAPConfig`.
ConfigT_contra = TypeVar('ConfigT_contra', bound='IMAPConfig',
                         contravariant=True)


class IMAPConfig:
    """Configurable settings that control how the IMAP server operates and what
    extensions it supports.

    Args:
        args: The command-line arguments.
        debug: If true, prints all socket activity to stdout.
        host: The IMAP server host.
        port: The IMAP server port.
        subsystem: The concurrency subsystem in use by the backend.
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
        max_idle_wait: If given, the ``IDLE`` command will transparently cancel
            and re-issue its request for updates every *N* seconds.
        extra: Additional keywords used for special circumstances.

    Attributes:
        args: The command-line arguments.

    """

    def __init__(self, args: Namespace, *,
                 debug: bool = False,
                 host: Optional[str] = None,
                 port: int = 143,
                 subsystem: Subsystem = None,
                 ssl_context: SSLContext = None,
                 starttls_enabled: bool = True,
                 reject_insecure_auth: bool = True,
                 preauth_credentials: AuthenticationCredentials = None,
                 max_append_len: Optional[int] = 1000000000,
                 bad_command_limit: Optional[int] = 5,
                 disable_search_keys: Iterable[bytes] = None,
                 disable_idle: bool = False,
                 max_idle_wait: float = None,
                 **extra: Any) -> None:
        super().__init__()
        self.args = args
        self.debug: Final = debug
        self.host: Final = host
        self.port: Final = port
        self.subsystem: Final = subsystem
        self.bad_command_limit: Final = bad_command_limit
        self.disable_search_keys: Final = disable_search_keys or []
        self.max_idle_wait: Final = max_idle_wait
        self._ssl_context = ssl_context
        self._starttls_enabled = starttls_enabled
        self._reject_insecure_auth = reject_insecure_auth
        self._preauth_credentials = preauth_credentials
        self._max_append_len = max_append_len
        self._disable_idle = disable_idle
        self._extra = extra

    @classmethod
    def parse_args(cls, args: Namespace) -> Mapping[str, Any]:
        """Given command-line arguments, return a dictionary of keywords that
        should be passed in to the :class:`IMAPConfig` (or sub-class)
        constructor. Sub-classes should override this method as needed.

        Args:
            args: The arguments parsed from the command-line.

        """
        return {}

    @classmethod
    def from_args(cls: Type[ConfigT], args: Namespace) -> ConfigT:
        """Build and return a new :class:`IMAPConfig` using command-line
        arguments.

        Args:
            args: The arguments parsed from the command-line.

        """
        parsed_args = cls.parse_args(args)
        return cls(args, debug=args.debug, host=args.host, port=args.port,
                   reject_insecure_auth=not args.insecure_login,
                   cert_file=args.cert, key_file=args.key,
                   **parsed_args)

    def apply_context(self) -> None:
        """Apply the configured settings to any :mod:`~pymap.context`
        variables.

        """
        if self.subsystem is not None:
            subsystem.set(self.subsystem)

    @property
    def ssl_context(self) -> Optional[SSLContext]:
        if self._ssl_context is None:
            cert_file: Optional[str] = self._extra.get('cert_file')
            if cert_file is None:
                return None
            key_file: str = self._extra.get('key_file', cert_file)
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
    def insecure_auth(self) -> SASLAuth:
        return SASLAuth()

    @property
    def preauth_credentials(self) -> Optional[AuthenticationCredentials]:
        return self._preauth_credentials

    @property
    def parsing_params(self) -> Params:
        return Params(max_append_len=self._max_append_len)

    @property
    def greeting(self) -> bytes:
        fqdn = socket.getfqdn().encode('ascii')
        return b'Server ready ' + fqdn

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
        ret = [b'LITERAL+']
        if self._starttls_enabled:
            ret.append(b'STARTTLS')
        return ret

    @property
    def max_filter_len(self) -> Optional[int]:
        return self._max_append_len
