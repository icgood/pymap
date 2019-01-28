"""IMAP server with pluggable Python backends."""

import asyncio
import logging
import traceback
from argparse import ArgumentParser, Namespace, ArgumentDefaultsHelpFormatter
from typing import Any, Type, Sequence, Mapping

from pkg_resources import iter_entry_points, DistributionNotFound

from . import __version__
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
    parser.add_argument('--no-service', dest='skip_services', action='append',
                        metavar='NAME', help='do not run the given service')
    subparsers = parser.add_subparsers(dest='backend',
                                       help='which pymap backend to use')

    backends: _Backends = _load_entry_points(parser, 'pymap.backend')
    services: _Services = _load_entry_points(parser, 'pymap.service')

    for backend_cls in backends.values():
        backend_cls.add_subparser(subparsers)
    for service_cls in services.values():
        service_cls.add_arguments(parser)
    parser.set_defaults(skip_services=[])
    args = parser.parse_args()

    log_level = logging.DEBUG if args.debug else logging.WARNING
    logging.basicConfig(level=log_level)

    if not args.backend:
        parser.error('Expected backend name')
    backend_type = backends[args.backend]

    service_types = [service for name, service in services.items()
                     if name not in args.skip_services]

    try:
        return asyncio.run(run(args, backend_type, service_types), debug=False)
    except KeyboardInterrupt:
        pass


async def run(args: Namespace, backend_type: Type[BackendInterface],
              service_types: Sequence[Type[ServiceInterface]]) -> None:
    backend = await backend_type.init(args)
    backend.config.apply_context()
    services = [await service.init(backend) for service in service_types]

    await asyncio.gather(*(service.run_forever() for service in services))


if __name__ == '__main__':
    main()
