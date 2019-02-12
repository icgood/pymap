"""Admin functions for a running pymap server."""

import asyncio
import sys
from argparse import ArgumentParser, Namespace, FileType
from typing import Type

from grpclib.client import Channel  # type: ignore
from pymap import __version__

from .append import AppendCommand
from .command import ClientCommand
from .. import AdminService
from ..grpc.admin_grpc import AdminStub


def main() -> int:
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('--version', action='version',
                        version='%(prog)s' + __version__)
    parser.add_argument('--outfile', metavar='PATH',
                        type=FileType('w'), default=sys.stdout,
                        help='the output file (default: stdout)')
    parser.add_argument('--socket', metavar='PATH', help='path to socket file')

    subparsers = parser.add_subparsers(dest='command',
                                       help='which admin command to run')
    commands = dict([AppendCommand.init(parser, subparsers)])
    args = parser.parse_args()

    if not args.command:
        parser.error('Expected command name.')
    command = commands[args.command]

    return asyncio.run(run(parser, args, command), debug=False)


async def run(parser: ArgumentParser, args: Namespace,
              command_cls: Type[ClientCommand]) -> int:
    loop = asyncio.get_event_loop()
    path = args.socket or AdminService.get_socket_path()
    channel = Channel(path=path, loop=loop)
    stub = AdminStub(channel)
    command = command_cls(stub, args)
    try:
        code = await command.run(args.outfile)
    finally:
        channel.close()
    return code
