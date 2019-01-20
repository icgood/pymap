"""IMAP server with pluggable Python backends."""

import asyncio
import logging
import traceback
from argparse import ArgumentParser, Namespace, ArgumentDefaultsHelpFormatter
from typing import Any, Type, Sequence, Mapping

from pkg_resources import iter_entry_points, DistributionNotFound

from .core import __version__
from .interfaces.backend import BackendInterface, ServiceInterface

_Backends = Mapping[str, Type[BackendInterface]]
_Services = Mapping[str, Type[ServiceInterface]]


def _load_entry_points(parser: ArgumentParser, group: str) \
        -> Mapping[str, Type[Any]]:
    ret = {}
    for entry_point in iter_entry_points(group):
        try:
            cls = entry_point.load()
        except DistributionNotFound:
            pass  # optional dependencies not installed
        except ImportError:
            traceback.print_exc()
            parser.exit(1, f'Error importing: {group}:{entry_point.name}\n')
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
    service = parser.add_argument_group('service arguments')
    service.add_argument('--no-services', action='store_true',
                         help='do not run any registered services')
    service.add_argument('--no-service', dest='skip_services', action='append',
                         help='do not run the given service')
    listener = parser.add_argument_group('server arguments')
    listener.add_argument('--port', action='store', type=int, default=1143,
                          help='the port to listen on')
    listener.add_argument('--cert', action='store', help='cert file for TLS')
    listener.add_argument('--key', action='store', help='key file for TLS')
    listener.add_argument('--insecure-login', action='store_true',
                          help='allow plaintext login without TLS')

    backends: _Backends = _load_entry_points(parser, 'pymap.backend')
    services: _Services = _load_entry_points(parser, 'pymap.service')

    for backend_cls in backends.values():
        backend_cls.add_subparser(subparsers)
    for service_cls in services.values():
        service_cls.add_arguments(parser)
    parser.set_defaults(skip_services=[])
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING)

    if not args.backend:
        parser.error('Expected backend name')
    backend = backends[args.backend]

    if not args.no_services:
        run_services = [service for name, service in services.items()
                        if name not in args.skip_services]
    else:
        run_services = []

    try:
        return asyncio.run(run(args, backend, run_services), debug=False)
    except KeyboardInterrupt:
        pass


async def run(args: Namespace, backend_type: Type[BackendInterface],
              service_types: Sequence[Type[ServiceInterface]]) -> None:
    backend = await backend_type.init(args)
    backend.config.apply_context()
    services = [await service.init(backend) for service in service_types]

    server = await asyncio.start_server(backend, port=args.port)

    # Typeshed currently has poor stubs for AbstractServer.
    async with server:  # type: ignore
        await asyncio.gather(server.serve_forever(),  # type: ignore
                             *(service.run_forever() for service in services))


if __name__ == '__main__':
    main()
