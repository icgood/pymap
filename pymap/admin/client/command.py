
from abc import abstractmethod
from argparse import ArgumentParser, Namespace
from typing import Any, Tuple
from typing_extensions import Protocol

from ..grpc.admin_grpc import AdminStub

__all__ = ['ClientCommand']


class ClientCommand(Protocol):

    @classmethod
    @abstractmethod
    def init(cls, parser: ArgumentParser, subparsers) \
            -> Tuple[str, 'ClientCommand']:
        """Initialize the client command, adding its subparser and returning
        the command name and object.

        Args:
            parser: The argument parser object.
            subparsers: The special action object as returned by
                :meth:`~argparse.ArgumentParser.add_subparsers`.

        """
        ...

    @abstractmethod
    async def run(self, stub: AdminStub, args: Namespace) -> Any:
        """Run the command and return its result.

        Args:
            stub: The GRPC stub for executing commands.
            args: The command line arguments.

        """
        ...
