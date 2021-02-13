
from __future__ import annotations

import os
import socket
import ssl
from abc import abstractmethod, ABCMeta
from argparse import Namespace
from collections.abc import Iterable, Iterator, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from ssl import SSLContext
from typing import Any, Final, TypeVar, Union, Optional

from proxyprotocol import ProxyProtocol
from proxyprotocol.version import ProxyProtocolVersion
from pysasl import SASLAuth, AuthenticationCredentials
from pysasl.hashing import HashInterface, get_hash

from .concurrent import Subsystem
from .context import subsystem
from .parsing import Params
from .parsing.commands import Commands

__all__ = ['ConfigT', 'ConfigT_contra', 'BackendCapability', 'IMAPConfig']

#: Type variable with an upper bound of :class:`IMAPConfig`.
ConfigT = TypeVar('ConfigT', bound='IMAPConfig')

#: Contravariant type variable with an upper bound of :class:`IMAPConfig`.
ConfigT_contra = TypeVar('ConfigT_contra', bound='IMAPConfig',
                         contravariant=True)


class BackendCapability(Iterable[bytes]):
    """Declares the IMAP capabilities that the backend supports.

    Args:
        idle: The ``IDLE`` extension is supported.
        object_id: The ``OBJECTID`` extension is supported.
        multi_append: The ``MULTIAPPEND`` extension is supported.
        custom: Optional list of custom capability strings to declare.

    """

    __slots__ = ['_capability']

    def __init__(self, *,
                 idle: bool,
                 object_id: bool,
                 multi_append: bool,
                 custom: Sequence[bytes] = None) -> None:
        super().__init__()
        capability: dict[bytes, bool] = {}
        if idle:
            capability[b'IDLE'] = True
        if object_id:
            capability[b'OBJECTID'] = True
        if multi_append:
            capability[b'MULTIAPPEND'] = True
        if custom is not None:
            for cap in custom:
                capability[cap] = True
        self._capability: Final = tuple(capability.keys())

    def __iter__(self) -> Iterator[bytes]:
        return iter(self._capability)

    def __eq__(self, other) -> bool:
        if isinstance(other, BackendCapability):
            return self._capability == other._capability
        if isinstance(other, tuple):
            return self._capability == other
        if isinstance(other, list):
            return list(self._capability) == other
        return super().__eq__(other)

    def __hash__(self) -> int:
        return hash(self._capability)

    def __repr__(self) -> str:
        return repr([cap.decode('ascii') for cap in self._capability])


class IMAPConfig(metaclass=ABCMeta):
    """Configurable settings that control how the IMAP server operates and what
    extensions it supports.

    Args:
        args: The command-line arguments.
        host: The IMAP server host.
        port: The IMAP server port or service name.
        debug: If true, prints all socket activity to stdout.
        subsystem: The concurrency subsystem in use by the backend.
        ssl_context: SSL context that will be used for opportunistic TLS.
            Alternatively, you can pass extra arguments ``cert_file`` and
            ``key_file`` and an SSL context will be created.
        starttls_enabled: True if opportunistic TLS should be supported.
        admin_key: The private admin key for unrestricted access by token.
        hash_context: The hash to use for passwords.
        cpu_subsystem: The subsystem to use for CPU-heavy operations,
            defaulting to a small thread pool.
        preauth_credentials: If given, clients will pre-authenticate on
            connection using these credentials.
        proxy_protocol: The PROXY protocol implementation to use.
        max_append_len: The maximum allowed length of the message body to an
            ``APPEND`` command.
        bad_command_limit: The number of consecutive commands received from
            the client with parsing errors before the client is disconnected.
        disable_idle: Disable the ``IDLE`` capability.
        extra: Additional keywords used for special circumstances.

    Attributes:
        args: The command-line arguments.

    """

    def __init__(self, args: Namespace, *,
                 host: Optional[str],
                 port: Union[str, int],
                 debug: bool = False,
                 subsystem: Subsystem = None,
                 ssl_context: SSLContext = None,
                 tls_enabled: bool = True,
                 secure_auth: bool = True,
                 preauth_credentials: AuthenticationCredentials = None,
                 proxy_protocol: ProxyProtocol = None,
                 admin_key: bytes = None,
                 hash_context: HashInterface = None,
                 cpu_subsystem: Subsystem = None,
                 max_append_len: Optional[int] = 1000000000,
                 bad_command_limit: Optional[int] = 5,
                 disable_search_keys: Iterable[bytes] = None,
                 disable_idle: bool = False,
                 **extra: Any) -> None:
        super().__init__()
        self.args = args
        self.debug: Final = debug
        self.host: Final = host
        self.port: Final = port
        self.subsystem: Final = subsystem
        self.bad_command_limit: Final = bad_command_limit
        self.disable_search_keys: Final = disable_search_keys or []
        self.admin_key: Final = admin_key
        self.hash_context: Final = hash_context or \
            get_hash(passlib_config=args.passlib_cfg)
        self.cpu_subsystem: Final = cpu_subsystem or \
            self._get_cpu_subsystem()
        self._ssl_context = ssl_context or self._load_certs(extra)
        self._tls_enabled = tls_enabled
        self._preauth_credentials = preauth_credentials
        self._proxy_protocol = proxy_protocol or \
            ProxyProtocolVersion.get(args.proxy_protocol)
        self._max_append_len = max_append_len

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
    def from_args(cls: type[ConfigT], args: Namespace,
                  **overrides: Any) -> ConfigT:
        """Build and return a new :class:`IMAPConfig` using command-line
        arguments.

        Args:
            args: The arguments parsed from the command-line.
            overrides: Override keyword arguments to the config constructor.

        """
        parsed_args = cls.parse_args(args)
        return cls(args, host=args.host, port=args.port, debug=args.debug,
                   cert_file=args.cert, key_file=args.key,
                   tls_enabled=args.tls, **parsed_args, **overrides)

    def apply_context(self) -> None:
        """Apply the configured settings to any :mod:`~pymap.context`
        variables.

        """
        if self.subsystem is not None:
            subsystem.set(self.subsystem)

    @property
    @abstractmethod
    def backend_capability(self) -> BackendCapability:
        """Allows backends to declare support for IMAP extensions and other
        capabilities.

        """
        ...

    @classmethod
    def _get_cpu_subsystem(cls) -> Subsystem:
        cpu_count = os.cpu_count() or 1
        cpus_minus_one = max(1, cpu_count - 1)
        executor = ThreadPoolExecutor(max_workers=cpus_minus_one)
        return Subsystem.for_threading(executor)

    @classmethod
    def _load_certs(cls, extra: Mapping[str, Any]) -> SSLContext:
        try:
            cert_file: Optional[str] = os.environ['CERT_FILE']
        except KeyError:
            cert_file = extra.get('cert_file')
        try:
            key_file: Optional[str] = os.environ['KEY_FILE']
        except KeyError:
            key_file = extra.get('key_file')
        ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        if cert_file is not None:
            ssl_context.load_cert_chain(cert_file, key_file)
        return ssl_context

    @property
    def ssl_context(self) -> SSLContext:
        return self._ssl_context

    @property
    def commands(self) -> Commands:
        return Commands()

    @property
    def initial_auth(self) -> SASLAuth:
        if self._tls_enabled:
            return SASLAuth([])
        else:
            return self.tls_auth

    @property
    def tls_auth(self) -> SASLAuth:
        return SASLAuth.defaults()

    @property
    def preauth_credentials(self) -> Optional[AuthenticationCredentials]:
        return self._preauth_credentials

    @property
    def proxy_protocol(self) -> ProxyProtocol:
        return self._proxy_protocol

    @property
    def parsing_params(self) -> Params:
        return Params(max_append_len=self._max_append_len)

    @property
    def greeting(self) -> bytes:
        try:
            fqdn = os.environ['FQDN']
        except KeyError:
            fqdn = socket.getfqdn()
        return b'Server ready ' + fqdn.encode('ascii')

    @property
    def login_capability(self) -> Sequence[bytes]:
        ret = [b'BINARY', b'UIDPLUS', b'MOVE', b'CHILDREN']
        if self._max_append_len is not None:
            ret.append(b'APPENDLIMIT=%i' % self._max_append_len)
        ret.extend(self.backend_capability)
        return ret

    @property
    def initial_capability(self) -> Sequence[bytes]:
        ret = [b'LITERAL+']
        if self._tls_enabled:
            ret.append(b'STARTTLS')
        return ret

    @property
    def max_filter_len(self) -> Optional[int]:
        return self._max_append_len
