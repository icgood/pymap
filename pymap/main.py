"""IMAP server with pluggable Python backends."""

import argparse
import asyncio
import logging
import logging.config
import os
from argparse import ArgumentParser, Namespace, ArgumentTypeError
from typing import Any, Type, Sequence, Mapping

from pkg_resources import iter_entry_points, DistributionNotFound

from . import __version__
from .interfaces.backend import BackendInterface, ServiceInterface

try:
    import systemd.daemon  # type: ignore
except ImportError:
    def notify_ready() -> None:
        pass
else:
    def notify_ready() -> None:
        systemd.daemon.notify('READY=1')

_Backends = Mapping[str, Type[BackendInterface]]
_Services = Mapping[str, Type[ServiceInterface]]


def main() -> None:
    parser = ArgumentParser(
        description=__doc__,
        fromfile_prefix_chars='@',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--debug', action='store_true',
                        help='increase printed output for debugging')
    parser.add_argument('--version', action='version',
                        version='%(prog)s ' + __version__)
    parser.add_argument('--set-uid', metavar='USER', type=_get_pwd,
                        help='drop privileges to user name or uid')
    parser.add_argument('--set-gid', metavar='GROUP', type=_get_grp,
                        help='drop privileges to group name or gid')
    parser.add_argument('--logging-cfg', metavar='PATH',
                        help='config file for logging')
    parser.add_argument('--no-service', dest='skip_services', action='append',
                        metavar='NAME', help='do not run the given service')
    subparsers = parser.add_subparsers(dest='backend',
                                       help='which pymap backend to use')

    backends: _Backends = _load_entry_points('pymap.backend')
    services: _Services = _load_entry_points('pymap.service')

    for backend_name, backend_cls in backends.items():
        backend_cls.add_subparser(backend_name, subparsers)
    for service_cls in services.values():
        service_cls.add_arguments(parser)
    parser.set_defaults(skip_services=[])
    args = parser.parse_args()

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
    notify_ready()
    await asyncio.gather(backend.task, *[service.task for service in services])


def _load_entry_points(group: str) -> Mapping[str, Type[Any]]:
    ret = {}
    for entry_point in iter_entry_points(group):
        try:
            cls = entry_point.load()
        except DistributionNotFound:
            pass  # optional dependencies not installed
        else:
            ret[entry_point.name] = cls
    return ret


def _get_pwd(setuid: str) -> int:
    from pwd import getpwnam, getpwuid
    try:
        try:
            uid = int(setuid)
        except ValueError:
            entry = getpwnam(setuid)
        else:
            entry = getpwuid(uid)
    except KeyError as exc:
        raise ArgumentTypeError(f'Invalid user: {setuid}') from exc
    else:
        return entry.pw_uid


def _get_grp(setgid: str) -> int:
    from grp import getgrnam, getgrgid
    try:
        try:
            gid = int(setgid)
        except ValueError:
            entry = getgrnam(setgid)
        else:
            entry = getgrgid(gid)
    except KeyError as exc:
        raise ArgumentTypeError(f'Invalid group: {setgid}') from exc
    else:
        return entry.gr_gid


def _drop_privileges(args: Namespace) -> None:
    if args.set_gid is not None:
        os.setgid(args.set_gid)
    if args.set_uid is not None:
        os.setuid(args.set_uid)
