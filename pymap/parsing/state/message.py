
from typing import Tuple, Type
from typing_extensions import Final

from . import ParsingExpectation
from ..message import AppendMessage, PreparedMessage

__all__ = ['ExpectPreparedMessage']


class ExpectPreparedMessage(ParsingExpectation[PreparedMessage]):
    """Indicates that the APPEND command has parsed a message that must be
    prepared before processing can proceed.

    Args:
        name: The destination mailbox name.
        append_msg: The appended message data.

    """

    __slots__ = ['mailbox', 'message']

    def __init__(self, mailbox: str, message: AppendMessage) -> None:
        super().__init__()
        self.mailbox: Final = mailbox
        self.message: Final = message

    @property
    def consume_args(self) -> Tuple[str, Type[PreparedMessage]]:
        return 'prepared_messages', PreparedMessage
