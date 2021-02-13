
from __future__ import annotations

from typing import Optional

from pymap.exceptions import AppendFailure
from pymap.interfaces.filter import FilterInterface, FilterCompilerInterface
from pymap.parsing.message import AppendMessage
from sievelib.parser import Parser

from .runner import SieveRunner
from .util import unquote

__all__ = ['SieveParseError', 'SieveCompiler', 'SieveFilter']


class SieveParseError(ValueError):
    """Parsing the sieve script failed."""
    pass


class SieveCompiler(FilterCompilerInterface[bytes]):
    """Compiles sieve scripts into :class:`SieveFilter` objects."""

    #: The list of Sieve extensions supported by the compiler.
    extensions: list[bytes] = [
        b'fileinto', b'reject', b'envelope', b'body']

    def __init__(self) -> None:
        super().__init__()
        self.parser = Parser()

    @property
    def value_type(self) -> type[bytes]:
        return bytes

    @property
    def filter_type(self) -> type[SieveFilter]:
        return SieveFilter

    async def compile(self, value: bytes) -> SieveFilter:
        parser = self.parser
        try:
            success = parser.parse(value)
        except Exception as exc:
            raise SieveParseError('Unhandled parsing error') from exc
        if success:
            runner = SieveRunner(parser.result)
            return SieveFilter(runner)
        else:
            raise SieveParseError(parser.error)


class SieveFilter(FilterInterface):
    """Filter implementation for applying sieve scripts to the appended
    message. The sieve script applies various conditions and controls to
    ultimately produce a set of actions to apply to the message.

    Args:
        runner: The sieve script runner.

    """

    def __init__(self, runner: SieveRunner) -> None:
        super().__init__()
        self.runner = runner

    async def apply(self, sender: str, recipient: str, mailbox: str,
                    append_msg: AppendMessage) \
            -> tuple[Optional[str], AppendMessage]:
        for action in self.runner.get_actions(sender, recipient, append_msg):
            if action.name == 'keep':
                pass
            elif action.name == 'fileinto':
                mailbox = unquote(action.arguments['mailbox'])
                return mailbox, append_msg
            elif action.name == 'reject':
                msg = unquote(action.arguments['text']).encode('utf-8')
                raise AppendFailure(mailbox, msg)
            elif action.name == 'discard':
                return None, append_msg
            else:
                msg = b'Unrecognized sieve action: %b' \
                    % action.name.encode('ascii')
                raise AppendFailure(mailbox, msg) from KeyError(action.name)
        return mailbox, append_msg
