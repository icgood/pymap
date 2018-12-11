
from abc import abstractmethod
from argparse import Namespace
from asyncio import StreamReader, StreamWriter
from typing_extensions import Protocol

from .session import LoginProtocol
from ..config import IMAPConfig

__all__ = ['BackendInterface']


class BackendInterface(Protocol):
    """Defines the abstract base class that is expected for backends that
    register themselves on the ``pymap.backend`` entry point.

    """

    @classmethod
    @abstractmethod
    def add_subparser(cls, subparsers) -> None:
        """Add a command-line argument sub-parser that will be used to choose
        this backend. For example::

            parser = subparsers.add_parser('foo', help='foo backend')
            parser.add_argument(...)

        Note:
            The name of the added sub-parser must be the same as the name of
            the entry point registered by the backend.

        Args:
            subparsers: The special action object as returned by
                :meth:`~argparse.ArgumentParser.add_subparsers`.

        """
        ...

    @classmethod
    @abstractmethod
    async def init(cls, args: Namespace) -> 'BackendInterface':
        """Initialize the backend and return an instance.

        Args:
            args: The command-line arguments.

        """
        ...

    @property
    @abstractmethod
    def login(self) -> LoginProtocol:
        """Login callback that takes authentication credentials and returns a
        :class:`~pymap.interfaces.session.SessionInterface` object.

        """
        ...

    @property
    @abstractmethod
    def config(self) -> IMAPConfig:
        """The IMAP config in use by the backend."""
        ...

    @abstractmethod
    async def __call__(self, reader: StreamReader, writer: StreamWriter) \
            -> None:
        """Client callback for :func:`~asyncio.start_server`. Most backends
        should inherit :class:`~pymap.server.IMAPServer` to implement this
        method.

        Args:
            reader: The socket input stream.
            writer: The socket output stream.

        """
        ...
