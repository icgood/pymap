
from __future__ import annotations

from . import CommandNonAuth, CommandNoArgs
from .. import Params, Space, EndLine
from ..primitives import Atom
from ..specials import AString

__all__ = ['AuthenticateCommand', 'LoginCommand', 'StartTLSCommand']


class AuthenticateCommand(CommandNonAuth):
    """The ``AUTHENTICATE`` command authenticates an IMAP session using a SASL
    mechanism.

    Args:
        tag: The command tag.
        mech_name: The SASL mechanism name.

    """

    command = b'AUTHENTICATE'

    def __init__(self, tag: bytes, mech_name: bytes) -> None:
        super().__init__(tag)
        self.mech_name = mech_name

    @classmethod
    def parse(cls, buf: memoryview, params: Params) \
            -> tuple[AuthenticateCommand, memoryview]:
        _, buf = Space.parse(buf, params)
        atom, after = Atom.parse(buf, params)
        _, after = EndLine.parse(after, params)
        return cls(params.tag, atom.value.upper()), after


class LoginCommand(CommandNonAuth):
    """The ``LOGIN`` command authenticates an IMAP session using a basic user
    ID and password credentials in clear-text.

    Args:
        tag: The command tag.
        userid: The user ID bytestring.
        password: The password bytestring.

    """

    command = b'LOGIN'

    def __init__(self, tag: bytes, userid: bytes, password: bytes) -> None:
        super().__init__(tag)
        self.userid = userid
        self.password = password

    @classmethod
    def parse(cls, buf: memoryview, params: Params) \
            -> tuple[LoginCommand, memoryview]:
        _, buf = Space.parse(buf, params)
        userid, buf = AString.parse(buf, params)
        _, buf = Space.parse(buf, params)
        password, buf = AString.parse(buf, params)
        _, buf = EndLine.parse(buf, params)
        return cls(params.tag, userid.value, password.value), buf


class StartTLSCommand(CommandNoArgs, CommandNonAuth):
    """The ``STARTTLS`` command attempts to encrypt a non-encrypted IMAP
    session using opportunistic TLS. The client/server handshake should take
    place immediately after the server issues a
    :class:`~pymap.parsing.response.ResponseOk`.

    """

    command = b'STARTTLS'
