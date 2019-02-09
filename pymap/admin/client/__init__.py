"""Admin functions for a running pymap server."""

import asyncio
import os
import os.path
from argparse import ArgumentParser, Namespace

from grpclib.client import Channel  # type: ignore
from pymap import __version__

from .append import AppendCommand
from .command import ClientCommand
from .. import AdminService
from ..grpc.admin_grpc import AdminStub


def _find_path(parser: ArgumentParser) -> str:
    for path in AdminService.get_socket_paths():
        if os.path.exists(path):
            return path
    parser.error('Cannot determine admin socket path')


def main() -> None:
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('--version', action='version',
                        version='%(prog)s' + __version__)
    parser.add_argument('--socket', metavar='PATH', help='path to socket file')

    subparsers = parser.add_subparsers(dest='command',
                                       help='which admin command to run')
    commands = dict([AppendCommand.init(parser, subparsers)])
    args = parser.parse_args()

    if not args.command:
        parser.error('Expected command name.')
    command = commands[args.command]

    asyncio.run(run(parser, args, command), debug=False)


async def run(parser: ArgumentParser, args: Namespace,
              command: ClientCommand) -> None:
    loop = asyncio.get_event_loop()
    path = args.socket or _find_path(parser)
    channel = Channel(path=path, loop=loop)
    stub = AdminStub(channel)
    try:
        ret = await command.run(stub, args)
        print(ret)
    finally:
        channel.close()
