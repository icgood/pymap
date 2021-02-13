
from __future__ import annotations

import enum
from collections.abc import Sequence
from typing import Union, Optional

__all__ = ['AddressPart', 'MatchType', 'SizeComparator', 'str_list', 'unquote']


class AddressPart(enum.Enum):
    LOCALPART = enum.auto()
    DOMAIN = enum.auto()
    ALL = enum.auto()

    @classmethod
    def of(cls, flag: Optional[str]) -> AddressPart:
        if not flag:
            return cls.ALL
        elif flag == ':localpart':
            return cls.LOCALPART
        elif flag == ':domain':
            return cls.DOMAIN
        elif flag == ':all':
            return cls.ALL
        else:
            raise NotImplementedError(flag)


class MatchType(enum.Enum):
    IS = enum.auto()
    CONTAINS = enum.auto()
    MATCHES = enum.auto()

    @classmethod
    def of(cls, flag: Optional[str]) -> MatchType:
        if not flag:
            return cls.IS
        elif flag == ':is':
            return cls.IS
        elif flag == ':contains':
            return cls.CONTAINS
        elif flag == ':matches':
            return cls.MATCHES
        else:
            raise NotImplementedError(flag)


class SizeComparator(enum.Enum):
    OVER = enum.auto()
    UNDER = enum.auto()

    @classmethod
    def of(cls, flag: str) -> SizeComparator:
        if flag == ':over':
            return cls.OVER
        elif flag == ':under':
            return cls.UNDER
        else:
            raise NotImplementedError(flag)


def str_list(value: Union[str, Sequence[str]]) -> Sequence[str]:
    if isinstance(value, str):
        return [unquote(value)]
    else:
        return [unquote(val) for val in value]


def unquote(value: str) -> str:
    if value[0] == '"' and value[-1] == '"':
        return value[1:-1]
    else:
        return value
