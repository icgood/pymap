"""IMAP server with pluggable Python backends."""

import argparse
import asyncio
import logging
import logging.config
import os
import shlex
from argparse import ArgumentParser, Namespace
from grp import getgrnam
from itertools import chain
from pwd import getpwnam
from typing import Any, Type, Optional, Sequence, Mapping

from pkg_resources import iter_entry_points, DistributionNotFound

from . import __version__
from .interfaces.backend import BackendInterface, ServiceInterface

_Backends = Mapping[str, Type[BackendInterface]]
_Services = Mapping[str, Type[ServiceInterface]]


def _load_entry_points(group: str) \
        -> Mapping[str, Type[Any]]:
    ret = {}
    for entry_point in iter_entry_points(group):
        try:
            cls = entry_point.load()
        except DistributionNotFound:
            pass  # optional dependencies not installed
        else:
            ret[entry_point.name] = cls
    return ret


def _get_argv() -> Optional[Sequence[str]]:
    pre_parser = ArgumentParser(add_help=False)
    pre_parser.add_argument('--args', nargs=argparse.REMAINDER)
    pre_args, _ = pre_parser.parse_known_args()
    if pre_args.args:
        args = pre_args.args
        return list(chain.from_iterable(shlex.split(arg) for arg in args))
    else:
        return None


def _drop_privileges(args: Namespace) -> None:
    if args.set_gid is not None:
        try:
            gid = int(args.set_gid)
        except ValueError:
            gid = getgrnam(args.set_gid).gr_gid
        os.setgid(gid)
    if args.set_uid is not None:
        try:
            uid = int(args.set_uid)
        except ValueError:
            uid = getpwnam(args.set_uid).pw_uid
        os.setuid(uid)


def main() -> None:
    parser = ArgumentParser(
        description=__doc__,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--debug', action='store_true',
                        help='increase printed output for debugging')
    parser.add_argument('--version', action='version',
                        version='%(prog)s ' + __version__)
    parser.add_argument('--args', nargs=argparse.REMAINDER,
                        help='additional command-line arguments')
    parser.add_argument('--set-uid', metavar='USER',
                        help='drop privileges to user name or uid')
    parser.add_argument('--set-gid', metavar='GROUP',
                        help='drop privileges to group name or gid')
    parser.add_argument('--logging-cfg', metavar='PATH',
                        help='config file for logging')
    parser.add_argument('--no-service', dest='skip_services', action='append',
                        metavar='NAME', help='do not run the given service')
    subparsers = parser.add_subparsers(dest='backend',
                                       help='which pymap backend to use')

    backends: _Backends = _load_entry_points('pymap.backend')
    services: _Services = _load_entry_points('pymap.service')

    for backend_cls in backends.values():
        backend_cls.add_subparser(subparsers)
    for service_cls in services.values():
        service_cls.add_arguments(parser)
    parser.set_defaults(skip_services=[])
    args = parser.parse_args(_get_argv())

    if args.logging_cfg:
        logging.config.fileConfig(args.logging_config)
    else:
        logging.basicConfig(level=logging.WARNING)
    if args.debug:
        logging.getLogger(__package__).setLevel(logging.DEBUG)

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
    backend, config = await backend_type.init(args)
    config.apply_context()
    services = [await service.start(backend, config)
                for service in service_types]

    _drop_privileges(args)
    await asyncio.gather(*[service.task for service in services])
