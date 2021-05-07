"""IMAP server with pluggable Python backends."""

from __future__ import annotations

import argparse
import asyncio
import logging
import logging.config
import os
import signal
from argparse import ArgumentParser, Namespace, ArgumentTypeError
from asyncio import CancelledError
from collections.abc import Sequence
from contextlib import nullcontext, suppress, AsyncExitStack
from string import Template

from . import __version__
from .backend import backends
from .interfaces.backend import BackendInterface, ServiceInterface
from .service import services

try:
    import systemd.daemon
except ImportError:
    def notify_ready() -> None:
        pass
else:
    def notify_ready() -> None:
        systemd.daemon.notify('READY=1')

try:
    from pid import PidFile
except ImportError:
    def PidFile(*args, **kwargs):
        return nullcontext()

try:
    import passlib
except ImportError:
    passlib = None


def main() -> None:
    parser = _PymapArgumentParser(description=__doc__)
    parser.add_argument('--debug', action='store_true',
                        help='increase printed output for debugging')
    parser.add_argument('--version', action='version',
                        version='%(prog)s ' + __version__)
    parser.add_argument('--pid-file', metavar='NAME',
                        help='change the filename of the PID file')
    parser.add_argument('--set-uid', metavar='USER', type=_get_pwd,
                        help='drop privileges to user name or uid')
    parser.add_argument('--set-gid', metavar='GROUP', type=_get_grp,
                        help='drop privileges to group name or gid')
    parser.add_argument('--logging-cfg', metavar='PATH',
                        help='config file for logging')
    parser.add_argument('--no-service', dest='skip_services', action='append',
                        metavar='NAME', help='do not run the given service')
    if passlib is not None:
        parser.add_argument('--passlib-cfg', metavar='PATH',
                            help='config file for passlib hashing')
    subparsers = parser.add_subparsers(dest='backend', required=True,
                                       metavar='BACKEND')

    for backend_name, backend_type in backends:
        subparser = backend_type.add_subparser(backend_name, subparsers)
        subparser.set_defaults(backend_type=backend_type)
    for _, service_type in services:
        service_type.add_arguments(parser)
    parser.set_defaults(skip_services=[], passlib_cfg=None)
    args = parser.parse_args()

    if args.logging_cfg:
        logging.config.fileConfig(args.logging_cfg)
    else:
        logging.basicConfig(level=logging.WARNING)
    if args.debug:
        logging.getLogger(__package__).setLevel(logging.DEBUG)

    service_types = [service for name, service in services
                     if name not in args.skip_services]
    with PidFile(pidname=args.pid_file, force_tmpdir=True):
        return asyncio.run(run(args, args.backend_type, service_types),
                           debug=False)


async def run(args: Namespace, backend_type: type[BackendInterface],
              service_types: Sequence[type[ServiceInterface]]) -> None:
    loop = asyncio.get_running_loop()
    backend, config = await backend_type.init(args)
    config.apply_context()

    services = [svc_type(backend, config) for svc_type in service_types]
    async with AsyncExitStack() as stack:
        await backend.start(stack)
        for service in services:
            await service.start(stack)

        _drop_privileges(args)
        notify_ready()
        forever = asyncio.create_task(_sleep_forever())
        loop.add_signal_handler(signal.SIGINT, forever.cancel)
        loop.add_signal_handler(signal.SIGTERM, forever.cancel)
        await forever


async def _sleep_forever() -> None:
    with suppress(CancelledError):
        while True:
            await asyncio.sleep(60.0)
    print()


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


class _PymapArgumentParser(ArgumentParser):

    def __init__(self, **extra) -> None:
        formatter_class = argparse.ArgumentDefaultsHelpFormatter
        super().__init__(fromfile_prefix_chars='@',
                         formatter_class=formatter_class,
                         **extra)

    def convert_arg_line_to_args(self, arg_line: str) -> list[str]:
        try:
            return [Template(arg_line).substitute(os.environ)]
        except KeyError as exc:
            raise EnvironmentError(
                f'Missing environment variable: ${exc.args[0]}') from exc
