
from typing import TypeVar, Tuple, AsyncIterable, AsyncIterator

__all__ = ['asyncenumerate', 'AsyncEnumerateT']

#: Type variable bound to the enumerated element in :func:`asyncenumerate`.
AsyncEnumerateT = TypeVar('AsyncEnumerateT')


class _AsyncEnumerateIterator(AsyncIterator[Tuple[int, AsyncEnumerateT]]):

    def __init__(self, iterator: AsyncIterator[AsyncEnumerateT],
                 idx: int) -> None:
        super().__init__()
        self._iter = iterator
        self._idx = idx

    def __aiter__(self) -> AsyncIterator[Tuple[int, AsyncEnumerateT]]:
        return self

    async def __anext__(self) -> Tuple[int, AsyncEnumerateT]:
        item = await self._iter.__anext__()
        self._idx += 1
        return self._idx, item


class _AsyncEnumerate(AsyncIterable[Tuple[int, AsyncEnumerateT]]):
    """Imitates Python's :func:`enumerate` with async iterators.

    Args:
        iterable: The iterable to enumerate over.
        start: The starting value of the index.

    """

    def __init__(self, iterable: AsyncIterable[AsyncEnumerateT],
                 start: int = 0) -> None:
        super().__init__()
        self._sub_iter = iterable
        self._start = start - 1

    def __aiter__(self) -> AsyncIterator[Tuple[int, AsyncEnumerateT]]:
        sub_iter = self._sub_iter.__aiter__()
        return _AsyncEnumerateIterator(sub_iter, self._start)


# Expose _AsyncEnumerate class with a public alias.
asyncenumerate = _AsyncEnumerate
