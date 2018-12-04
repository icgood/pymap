"""IMAP server with pluggable Python backends."""

import asyncio
import traceback
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
from typing import Mapping, Type

from pkg_resources import iter_entry_points

from .core import __version__
from .interfaces.backend import BackendInterface


def _load_backends(parser: ArgumentParser) \
        -> Mapping[str, Type[BackendInterface]]:
    ret = {}
    for entry_point in iter_entry_points('pymap.backend'):
        try:
            cls = entry_point.load()
        except ImportError:
            traceback.print_exc()
            parser.exit(1, 'Error importing registered backend: %s\n'
                        % entry_point.name)
        else:
            ret[entry_point.name] = cls
    return ret


def main() -> None:
    parser = ArgumentParser(description=__doc__,
                            formatter_class=ArgumentDefaultsHelpFormatter)
    parser.add_argument('--debug', action='store_true',
                        help='increase printed output for debugging')
    parser.add_argument('--version', action='version',
                        version='%(prog)s' + __version__)
    subparsers = parser.add_subparsers(dest='backend',
                                       help='which pymap backend to use')
    listener = parser.add_argument_group('server arguments')
    listener.add_argument('--port', action='store', type=int, default=1143,
                          help='the port to listen on')
    listener.add_argument('--cert', action='store', help='cert file for TLS')
    listener.add_argument('--key', action='store', help='key file for TLS')
    listener.add_argument('--insecure-login', action='store_true',
                          help='allow plaintext login without TLS')

    backends = _load_backends(parser)

    for cls in backends.values():
        cls.add_subparser(subparsers)
    args = parser.parse_args()

    try:
        backend = backends[args.backend]
    except KeyError:
        parser.error('Expected backend name.')
        return

    loop = asyncio.get_event_loop()
    callback = loop.run_until_complete(backend.init(args))
    coro = asyncio.start_server(callback, port=args.port, loop=loop)
    server = loop.run_until_complete(coro)

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        print()

    server.close()
    loop.run_until_complete(server.wait_closed())
    loop.close()


if __name__ == '__main__':
    main()
