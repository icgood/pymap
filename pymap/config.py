import os.path
import ssl
from argparse import Namespace
from ssl import SSLContext
from typing import overload, Sequence, Any, Optional

from pysasl import SASLAuth

from .parsing import Params
from .parsing.commands import Commands

__all__ = ['IMAPConfig']


class IMAPConfig:
    """Configurable settings that control how the IMAP server operates and what
    extensions it supports.

    Args:
        debug: If true, prints all socket activity to stdout.
        ssl_context: SSL context that will be used for opportunistic TLS.
            Alternatively, you can pass extra arguments ``cert_file`` and
            ``key_file`` and an SSL context will be created.
        starttls_enabled: True if opportunistic TLS should be supported.
        reject_insecure_auth: True if authentication mechanisms that transmit
            credentials in cleartext should be rejected on non-encrypted
            transports.
        max_append_len: The maximum allowed length of the message body to an
            ``APPEND`` command.
        bad_command_limit: The number of consecutive commands received from
            the client with parsing errors before the client is disconnected.
        extra: Additional keywords used for special circumstances.

    """

    def __init__(self, debug: bool = False,
                 ssl_context: SSLContext = None,
                 starttls_enabled: bool = True,
                 reject_insecure_auth: bool = True,
                 max_append_len: Optional[int] = 1000000000,
                 bad_command_limit: Optional[int] = 5,
                 **extra: Any) -> None:
        super().__init__()
        self._debug = debug
        self._ssl_context = ssl_context
        self._starttls_enabled = starttls_enabled
        self._reject_insecure_auth = reject_insecure_auth
        self._max_append_len = max_append_len
        self._bad_command_limit = bad_command_limit
        self._extra = extra

    @classmethod
    def from_args(cls, args: Namespace) -> 'IMAPConfig':
        """Build and return a new :class:`IMAPConfig` using command-line
        arguments.

        Args:
            args: The arguments parsed from the command-line.

        """
        return IMAPConfig(debug=args.debug,
                          cert_file=args.cert,
                          key_file=args.key)

    @overload  # noqa
    def get_extra(self, key: str, fallback: None) -> Optional[str]:
        ...

    @overload  # noqa
    def get_extra(self, key: str, fallback: str) -> str:
        ...

    def get_extra(self, key, fallback):  # noqa
        return self._extra.get(key, fallback)

    @property
    def debug(self) -> bool:
        return self._debug

    @property
    def bad_command_limit(self) -> Optional[int]:
        return self._bad_command_limit

    @property
    def ssl_context(self) -> Optional[SSLContext]:
        if self._ssl_context is None:
            cert_file = self.get_extra('cert_file', None)
            if cert_file is None:
                return None
            key_file: str = self.get_extra('key_file', cert_file)
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
    def static_capability(self) -> Sequence[bytes]:
        ret = [b'BINARY', b'UIDPLUS', b'MULTIAPPEND']
        if self._max_append_len is not None:
            ret.append(b'APPENDLIMIT=%i' % self._max_append_len)
        return ret

    @property
    def parsing_params(self) -> Params:
        return Params(max_append_len=self._max_append_len)

    @property
    def initial_capability(self) -> Sequence[bytes]:
        ret = []
        if self._starttls_enabled:
            ret.append(b'STARTTLS')
        if self._reject_insecure_auth:
            ret.append(b'LOGINDISABLED')
        return ret
