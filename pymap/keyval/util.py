
from typing import TypeVar, Tuple, AsyncIterable, AsyncIterator

__all__ = ['asyncenumerate']

_ElementT = TypeVar('_ElementT')


class _AsyncEnumerateIterator(AsyncIterator[Tuple[int, _ElementT]]):

    def __init__(self, iterator: AsyncIterator[_ElementT], idx: int) -> None:
        super().__init__()
        self._iter = iterator
        self._idx = idx

    def __aiter__(self) -> AsyncIterator[Tuple[int, _ElementT]]:
        return self

    async def __anext__(self) -> Tuple[int, _ElementT]:
        item = await self._iter.__anext__()
        self._idx += 1
        return self._idx, item


class _AsyncEnumerate(AsyncIterable[Tuple[int, _ElementT]]):

    def __init__(self, iterable: AsyncIterable[_ElementT], start: int) -> None:
        super().__init__()
        self._sub_iter = iterable
        self._start = start - 1

    def __aiter__(self) -> AsyncIterator[Tuple[int, _ElementT]]:
        sub_iter = self._sub_iter.__aiter__()
        return _AsyncEnumerateIterator(sub_iter, self._start)


def asyncenumerate(iterable: AsyncIterable[_ElementT],
                   start: int = 0) -> _AsyncEnumerate[_ElementT]:
    """Imitates Python's :func:`enumerate` with async iterators.

    Args:
        iterable: The iterable to enumerate over.
        start: The starting value of the index.

    """
    return _AsyncEnumerate(iterable, start)
