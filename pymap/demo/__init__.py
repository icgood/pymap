from pymap.interfaces.login import LoginProtocol
from .session import Session
from .state import State

__all__ = ['add_subparser', 'init']


def add_subparser(subparsers):
    subparsers.add_parser('demo', help='In-memory demo backend.')


def init(*_) -> LoginProtocol:
    State.init()
    return Session.login
