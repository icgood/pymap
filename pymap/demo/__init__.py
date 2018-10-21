from typing import Tuple, Type

from pymap.config import IMAPConfig
from pymap.interfaces.login import LoginProtocol
from .session import Session
from .state import State

__all__ = ['add_subparser', 'init']


def add_subparser(subparsers):
    subparsers.add_parser('demo', help='In-memory demo backend.')


def init(*_) -> Tuple[LoginProtocol, Type[IMAPConfig]]:
    State.init()
    return Session.login, IMAPConfig
