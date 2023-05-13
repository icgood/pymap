
from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from . import CommandAny, CommandNoArgs
from .. import Space, EndLine, Params
from ..exceptions import NotParseable
from ..primitives import Nil, List, String

__all__ = ['CapabilityCommand', 'LogoutCommand', 'NoOpCommand', 'IdCommand']


class CapabilityCommand(CommandNoArgs, CommandAny):
    """The ``CAPABILITY`` command lists current server capabilities."""

    command = b'CAPABILITY'


class LogoutCommand(CommandNoArgs, CommandAny):
    """The ``LOGOUT`` command ends the IMAP session."""

    command = b'LOGOUT'


class NoOpCommand(CommandNoArgs, CommandAny):
    """The ``NOOP`` command does nothing, but can be used to check for state
    changes on a selected mailbox.

    """

    command = b'NOOP'


class IdCommand(CommandAny):
    """The ``ID`` command allows the client and server to provide each other
    information for statistical purposes and bug reporting.

    See Also:
        `RFC 2971 <https://tools.ietf.org/html/rfc2971>`_

    Args:
        tag: The command tag.
        parameters: A mapping of the keys and values provided by the client.

    """

    command = b'ID'

    def __init__(self, tag: bytes, parameters: Mapping[bytes, bytes] | None) \
            -> None:
        super().__init__(tag)
        self.parameters: Final = parameters

    @classmethod
    def parse(cls, buf: memoryview, params: Params) \
            -> tuple[IdCommand, memoryview]:
        _, buf = Space.parse(buf, params)
        parameters: Mapping[bytes, bytes] | None = None
        try:
            _, buf = Nil.parse(buf, params)
        except NotParseable:
            parameters, buf = cls._parse_list(buf, params)
        _, buf = EndLine.parse(buf, params)
        return cls(params.tag, parameters), buf

    @classmethod
    def _parse_list(cls, buf: memoryview, params: Params) \
            -> tuple[Mapping[bytes, bytes], memoryview]:
        params_copy = params.copy(expected=[String], list_limit=60)
        keyval_list, buf = List.parse(buf, params_copy)
        keyval_iter = iter(item.value for item in
                           keyval_list.get_as(String))
        try:
            parameters = dict(zip(keyval_iter, keyval_iter, strict=True))
        except ValueError as exc:
            raise NotParseable(buf) from exc
        return parameters, buf
