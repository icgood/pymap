"""Admin functions for a running pymap server."""

from __future__ import annotations

import asyncio
import sys
from argparse import ArgumentParser, Namespace, FileType
from typing import Type, Mapping

from grpclib.client import Channel
from pkg_resources import iter_entry_points, DistributionNotFound
from pymap import __version__

from .command import ClientCommand
from ..grpc.admin_grpc import AdminStub


def main() -> int:
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('--version', action='version',
                        version='%(prog)s' + __version__)
    parser.add_argument('--outfile', metavar='PATH',
                        type=FileType('w'), default=sys.stdout,
                        help='the output file (default: stdout)')
    parser.add_argument('--host', metavar='HOST', default='localhost',
                        help='host to connect to')
    parser.add_argument('--port', metavar='PORT', type=int, default=9090,
                        help='port to connect to')

    subparsers = parser.add_subparsers(dest='command',
                                       help='which admin command to run')
    commands = _load_entry_points('pymap.admin.client')
    for command_name, command_cls in commands.items():
        command_cls.add_subparser(command_name, subparsers)
    args = parser.parse_args()

    if not args.command:
        parser.error('Expected command name.')
    command = commands[args.command]

    return asyncio.run(run(parser, args, command), debug=False)


async def run(parser: ArgumentParser, args: Namespace,
              command_cls: Type[ClientCommand]) -> int:
    loop = asyncio.get_event_loop()
    channel = Channel(host=args.host, port=args.port, loop=loop)
    stub = AdminStub(channel)
    command = command_cls(stub, args)
    try:
        code = await command.run(args.outfile)
    finally:
        channel.close()
    return code


def _load_entry_points(group: str) -> Mapping[str, Type[ClientCommand]]:
    ret = {}
    for entry_point in iter_entry_points(group):
        try:
            cls = entry_point.load()
        except DistributionNotFound:
            pass  # optional dependencies not installed
        else:
            ret[entry_point.name] = cls
    return ret
