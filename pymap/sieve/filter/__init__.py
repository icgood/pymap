
from typing import Optional, Tuple

from pymap.exceptions import AppendFailure
from pymap.interfaces.filter import FilterInterface
from pymap.interfaces.session import AppendMessage
from sievelib.parser import Parser  # type: ignore

from .runner import SieveRunner
from .util import unquote

__all__ = ['SieveParseError', 'SieveFilter']


class SieveParseError(ValueError):
    """Parsing the sieve script failed."""
    pass


class SieveFilter(FilterInterface):
    """Filter implementation for applying sieve scripts to the appended
    message. The sieve script applies various conditions and controls to
    ultimately produce a set of actions to apply to the message.

    Args:
        script: The sieve script contents.

    """

    def __init__(self, script: bytes) -> None:
        super().__init__()
        self._script = script
        self._runner: Optional[SieveRunner] = None

    @property
    def runner(self) -> SieveRunner:
        if self._runner is None:
            p = Parser()
            if p.parse(self._script):
                self._runner = SieveRunner(p.result)
            else:
                raise SieveParseError(p.error)
        return self._runner

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
