
from __future__ import annotations

from abc import abstractmethod, ABCMeta
from typing import TypeVar, Generic, Any, Type, Optional, Tuple, Sequence
from typing_extensions import Final

__all__ = ['ParsingExpectedT', 'ParsingState', 'ParsingInterrupt',
           'ParsingExpectation']

#: Type variable for expected data during parsing.
ParsingExpectedT = TypeVar('ParsingExpectedT')


class ParsingState:
    """Contains mutable parsing state. As parsing advances, it may need
    external data to proceed. Because parsing is linear, these expectations
    are defined as a mapping of an key string to a sequence of objects.

    Warning:
        The expectation keys and object types are dynamic, to prevent cyclic
        dependencies in the parsing system.

    See Also:
        :class:`pymap.parsing.interrupts.ParsingInterrupt`

    Args:
        expectations: The expect

    """

    __slots__ = ['_expectations', '_iters']

    def __init__(self, **expectations: Sequence[Any]) \
            -> None:
        super().__init__()
        self._iters = {key: iter(val) for key, val in expectations.items()}

    def consume(self, key: str, cls: Type[ParsingExpectedT]) \
            -> Optional[ParsingExpectedT]:
        """Consume and return a piece of data, if available.

        Args:
            key: The expectation key.

        """
        try:
            return next(self._iters[key])
        except (KeyError, StopIteration):
            return None


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

    @property
    @abstractmethod
    def consume_args(self) -> Tuple[str, Type[ParsingExpectedT]]:
        """Tuple of the *key* and *cls* arguments to pass to
        :meth:`~ParsingState.consume`.

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
        next_val = state.consume(*self.consume_args)
        if next_val is None:
            raise ParsingInterrupt(self)
        else:
            return next_val
