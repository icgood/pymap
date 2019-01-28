
from abc import abstractmethod
from argparse import Namespace, ArgumentParser
from typing_extensions import Protocol

from .session import LoginProtocol
from ..config import IMAPConfig

__all__ = ['BackendInterface', 'ServiceInterface']


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


class ServiceInterface(Protocol):
    """Defines the abstract base class that is expected for services that
    register themselves on the ``pymap.service`` entry point.

    """

    @classmethod
    @abstractmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        """Add the arguments or argument group used to configure the service.
        For example::

            group = parser.add_argument_group('foo service arguments')
            group.add_argument(...)

        Args:
            parser: The argument parser.

        """
        ...

    @classmethod
    @abstractmethod
    async def init(cls, backend: BackendInterface) -> 'ServiceInterface':
        """Initialize service and return the instance.

        Args:
            backend: The backend object.

        """
        ...

    @abstractmethod
    async def run_forever(self) -> None:
        """Start and run the service indefinitely. This coroutine should
        gracefully exit if :exc:`~asyncio.CancelledError` is raised.

        """
        ...
