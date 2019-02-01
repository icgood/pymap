
from typing import Optional, Tuple

from pymap.exceptions import AppendFailure
from pymap.filter import FilterCompiler
from pymap.interfaces.filter import FilterInterface
from pymap.interfaces.session import AppendMessage
from sievelib.parser import Parser  # type: ignore

from .runner import SieveRunner
from .util import unquote

__all__ = ['SieveParseError' 'SieveCompiler', 'SieveFilter']


class SieveParseError(ValueError):
    """Parsing the sieve script failed."""
    pass


class SieveCompiler(FilterCompiler[bytes]):
    """Compiles sieve scripts into :class:`SieveFilter` objects."""

    def __init__(self) -> None:
        super().__init__()
        self.parser = Parser()

    async def compile(self, value: bytes) -> 'SieveFilter':
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
            -> Tuple[Optional[str], AppendMessage]:
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
