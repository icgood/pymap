from argparse import Namespace
from typing import Tuple

from pymap.config import IMAPConfig
from pymap.interfaces.session import LoginProtocol
from .session import Session
from .state import State

__all__ = ['add_subparser', 'init']


def add_subparser(subparsers) -> None:
    subparsers.add_parser('demo', help='In-memory demo backend.')


def init(args: Namespace) -> Tuple[LoginProtocol, IMAPConfig]:
    State.init()
    return Session.login, IMAPConfig.from_args(args)
