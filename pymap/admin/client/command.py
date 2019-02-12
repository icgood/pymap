
from abc import abstractmethod, ABCMeta
from argparse import ArgumentParser, Namespace
from typing import Type, Tuple, TextIO
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
    def init(cls, parser: ArgumentParser, subparsers) \
            -> Tuple[str, Type['ClientCommand']]:
        """Initialize the client command, adding its subparser and returning
        the command name and class.

        Args:
            parser: The argument parser object.
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
