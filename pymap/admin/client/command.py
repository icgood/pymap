
from __future__ import annotations

from abc import abstractmethod, ABCMeta
from argparse import Namespace
from typing import TextIO
from typing_extensions import Final

from ..grpc.admin_grpc import AdminStub

__all__ = ['ClientCommand']


class ClientCommand(metaclass=ABCMeta):
    """Interface for client command implementations.

    Args:
        stub: The GRPC stub for executing commands.
        args: The command line arguments.

    """

    def __init__(self, stub: AdminStub, args: Namespace) -> None:
        super().__init__()
        self.stub: Final = stub
        self.args: Final = args

    @classmethod
    @abstractmethod
    def add_subparser(cls, name: str, subparsers) -> None:
        """Add the command-line argument subparser for the command.

        Args:
            name: The name to use for the subparser.
            subparsers: The special action object as returned by
                :meth:`~argparse.ArgumentParser.add_subparsers`.

        """
        ...

    @abstractmethod
    async def run(self, fileobj: TextIO) -> int:
        """Run the command and return the exit code.

        Args:
            fileobj: The file object to print the output to.

        """
        ...
