
from __future__ import annotations

from abc import abstractmethod, ABCMeta
from argparse import Namespace, ArgumentParser
from collections.abc import Sequence
from contextlib import AsyncExitStack
from typing import Protocol, Any

from .login import LoginInterface
from ..config import IMAPConfig
from ..health import HealthStatusView

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
    async def init(cls, args: Namespace, **overrides: Any) \
            -> tuple[BackendInterface, IMAPConfig]:
        """Initialize the backend and return an instance.

        Args:
            args: The command-line arguments.
            overrides: Override keyword arguments to the config constructor.

        """
        ...

    @abstractmethod
    async def start(self, stack: AsyncExitStack) -> None:
        """Start the backend.

        Args:
            stack: An exit stack that should be used for cleanup.

        """
        ...

    @property
    @abstractmethod
    def login(self) -> LoginInterface:
        """Login interface that handles authentication credentials."""
        ...

    @property
    @abstractmethod
    def config(self) -> IMAPConfig:
        """The IMAP config in use by the backend."""
        ...

    @property
    @abstractmethod
    def status(self) -> HealthStatusView:
        """The health status view for the backend."""
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
    async def start(self, stack: AsyncExitStack) -> None:
        """Start the service.

        Args:
            stack: An exit stack that should be used for cleanup.

        """
        ...
