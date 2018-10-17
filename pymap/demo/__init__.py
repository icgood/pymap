from pymap.interfaces.session import LoginFunc
from .session import Session
from .state import State

__all__ = ['add_subparser', 'init']


def add_subparser(subparsers):
    subparsers.add_parser('demo')


def init(*_) -> LoginFunc:
    State.init()
    return Session.login
