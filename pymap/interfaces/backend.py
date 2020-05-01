
from __future__ import annotations

from abc import abstractmethod, ABCMeta
from argparse import Namespace, ArgumentParser
from typing import Any, Tuple, Sequence, Awaitable
from typing_extensions import Protocol

from .session import LoginProtocol
from ..config import IMAPConfig

__all__ = ['BackendInterface', 'ServiceInterface']


class BackendInterface(Protocol):
    """Defines the abstract base class that is expected for backends that
    register themselves on the ``pymap.backend`` entry point.

    """

    __slots__: Sequence[str] = []

    @classmethod
    @abstractmethod
    def add_subparser(cls, name: str, subparsers: Any) -> ArgumentParser:
        """Add a command-line argument sub-parser that will be used to choose
        this backend. For example::

            parser = subparsers.add_parser('foo', help='foo backend')
            parser.add_argument(...)

        Args:
            name: The name to use for the subparser.
            subparsers: The special action object as returned by
                :meth:`~argparse.ArgumentParser.add_subparsers`.

        Returns:
            The new sub-parser object.

        """
        ...

    @classmethod
    @abstractmethod
    async def init(cls, args: Namespace) \
            -> Tuple[BackendInterface, IMAPConfig]:
        """Initialize the backend and return an instance.

        Args:
            args: The command-line arguments.

        """
        ...

    @abstractmethod
    async def start(self, services: Sequence[ServiceInterface]) -> Awaitable:
        """Start the backend, as well as any services.

        Args:
            services: Available services that may also be started.

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


class ServiceInterface(metaclass=ABCMeta):
    """Defines the abstract base class that is expected for services that
    register themselves on the ``pymap.service`` entry point.

    """

    __slots__ = ['backend', 'config']

    def __init__(self, backend: BackendInterface, config: IMAPConfig) -> None:
        super().__init__()
        self.backend = backend
        self.config = config

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

    @abstractmethod
    async def start(self) -> Awaitable:
        """Start the service."""
        ...
