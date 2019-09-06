
from __future__ import annotations

from typing import Type, Tuple
from typing_extensions import Final

from . import ParsingExpectation

__all__ = ['ExpectContinuation']


class ExpectContinuation(ParsingExpectation[memoryview]):
    """Indicates that the buffer has been successfully parsed so far, but
    requires a continuation of the command from the client.

    Args:
        message: The message from the server.
        literal_length: If the continuation is for a string literal, this
            is the byte length to expect.

    """

    __slots__ = ['message', 'literal_length']

    def __init__(self, message: bytes, literal_length: int = 0) -> None:
        super().__init__()
        self.message: Final = message
        self.literal_length: Final = literal_length

    @property
    def consume_args(self) -> Tuple[str, Type[memoryview]]:
        return 'continuations', memoryview
