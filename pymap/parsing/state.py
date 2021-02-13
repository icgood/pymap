
from __future__ import annotations

from abc import abstractmethod, ABCMeta
from collections.abc import Sequence
from typing import TypeVar, Generic, Final, Optional

__all__ = ['ParsingExpectedT', 'ParsingState', 'ParsingInterrupt',
           'ParsingExpectation']

#: Type variable for expected data during parsing.
ParsingExpectedT = TypeVar('ParsingExpectedT')


class ParsingState:
    """Contains mutable parsing state. As parsing advances, it may need
    external data to proceed. Because parsing is linear, these expectations
    are defined as sequence of objects that are iterated during parsing.

    Warning:
        The expectation keys and object types are dynamic, to prevent cyclic
        dependencies in the parsing system.

    See Also:
        :class:`pymap.parsing.interrupts.ParsingInterrupt`

    Args:
        continuations: The IMAP literal string continuations.

    """

    __slots__ = ['continuations']

    def __init__(self, *, continuations: Sequence[memoryview] = None) -> None:
        super().__init__()
        self.continuations: Final = iter(continuations or ())


class ParsingInterrupt(Exception):
    """Exception thrown to interrupt the IMAP parsing process, because an
    expectation was not met. The caller should update provide an updated
    :class:`ParsingState` object that meets the expectation.

    Args:
        expected: The required data expectation.

    """

    __slots__ = ['expected']

    def __init__(self, expected: ParsingExpectation) -> None:
        super().__init__()
        self.expected: Final = expected


class ParsingExpectation(Generic[ParsingExpectedT], metaclass=ABCMeta):
    """Base class for parsing expectations that may require additional data
    before parsing can advance.

    """

    __slots__: Sequence[str] = []

    @abstractmethod
    def consume(self, state: ParsingState) -> Optional[ParsingExpectedT]:
        """Consume and return a piece of data, if available.

        Args:
            state: The parsing state.

        """
        ...

    def expect(self, state: ParsingState) -> ParsingExpectedT:
        """Indicates that the buffer has been successfully parsed so far, but
        additional data is expected from the parsing state.

        Args:
            state: The parsing state object.

        Raises:
            ParsingInterrupt: The expected data was not available.

        """
        next_val = self.consume(state)
        if next_val is None:
            raise ParsingInterrupt(self)
        else:
            return next_val


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

    def consume(self, state: ParsingState) -> Optional[memoryview]:
        return next(state.continuations, None)
