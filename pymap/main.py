"""IMAP server with pluggable Python backends."""

import asyncio
import traceback
from argparse import ArgumentParser

from pkg_resources import iter_entry_points

from .core import __version__
from .server import IMAPServer


def _load_backends(parser):
    ret = {}
    for entry_point in iter_entry_points('pymap.backend'):
        try:
            mod = entry_point.load()
        except ImportError:
            traceback.print_exc()
            parser.exit(1, 'Error importing registered backend: %s\n'
                        % entry_point.name)
        else:
            ret[entry_point.name] = mod
    return ret


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('--debug', action='store_true',
                        help='increase printed output for debugging')
    parser.add_argument('--version', action='version',
                        version='%(prog)s' + __version__)
    subparsers = parser.add_subparsers(dest='backend',
                                       help='which pymap backend to use')
    listener = parser.add_argument_group('server arguments')
    listener.add_argument('--port', action='store', type=int, default=1143)
    listener.add_argument('--cert', action='store')
    listener.add_argument('--key', action='store')
    listener.add_argument('--insecure-login', action='store_true')

    backends = _load_backends(parser)

    for mod in backends.values():
        mod.add_subparser(subparsers)
    args = parser.parse_args()

    try:
        backend = backends[args.backend]
    except KeyError:
        parser.error('Expected backend name.')
        return

    loop = asyncio.get_event_loop()
    login_func, config = loop.run_until_complete(backend.init(args))
    callback = IMAPServer(login_func, config)
    coro = asyncio.start_server(callback, port=args.port, loop=loop)
    server = loop.run_until_complete(coro)

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        print()

    server.close()
    loop.run_until_complete(server.wait_closed())
    loop.close()
    return 0


if __name__ == '__main__':
    main()
