"""IMAP server with pluggable Python backends."""

import asyncio
import logging
import traceback
from argparse import ArgumentParser, Namespace, ArgumentDefaultsHelpFormatter
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

    logging.basicConfig(level=logging.WARNING)

    try:
        backend = backends[args.backend]
    except KeyError:
        parser.error('Expected backend name.')
    else:
        try:
            return asyncio.run(run(args, backend), debug=False)
        except KeyboardInterrupt:
            pass


async def run(args: Namespace, backend_cls: Type[BackendInterface]) -> None:
    backend = await backend_cls.init(args)
    backend.config.apply_context()

    server = await asyncio.start_server(backend, port=args.port)

    # Typeshed currently has poor stubs for AbstractServer.
    async with server:  # type: ignore
        await server.serve_forever()  # type: ignore
