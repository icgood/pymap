"""IMAP server with pluggable Python backends."""

import asyncio
from argparse import ArgumentParser

from pkg_resources import iter_entry_points

from .core import __version__
from .server import IMAPServer


def _load_backends():
    return {entry_point.name: entry_point.load() for entry_point in
            iter_entry_points('pymap.backend')}


def main():
    backends = _load_backends()

    parser = ArgumentParser(description=__doc__)
    parser.add_argument('--debug', action='store_true')
    parser.add_argument('--port', action='store', type=int, default=1143)
    parser.add_argument('--cert', action='store')
    parser.add_argument('--key', action='store')
    parser.add_argument('--version', action='version',
                        version='%(prog)s' + __version__)
    subparsers = parser.add_subparsers(dest='backend',
                                       help='Which pymap backend to use.')
    for mod in backends.values():
        mod.add_subparser(subparsers)
    args = parser.parse_args()

    try:
        backend = backends[args.backend]
    except KeyError:
        parser.error('Expected backend name.')
        return

    login_func, config_type = backend.init(args)
    config = config_type.from_args(args)

    callback = IMAPServer(login_func, config)
    loop = asyncio.get_event_loop()
    coro = asyncio.start_server(callback, port=args.port, loop=loop)
    server = loop.run_until_complete(coro)

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        print()

    server.close()
    loop.run_until_complete(server.wait_closed())
    loop.close()
