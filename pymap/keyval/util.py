
from typing import TypeVar, Tuple, AsyncIterable, AsyncIterator

__all__ = ['asyncenumerate']

_T = TypeVar('_T')
_TE = Tuple[int, _T]


class _AsyncEnumerateIterator(AsyncIterator[_TE]):

    def __init__(self, iterator: AsyncIterator[_T], idx: int) -> None:
        super().__init__()
        self._iter = iterator
        self._idx = idx

    def __aiter__(self) -> AsyncIterator[_TE]:
        return self

    async def __anext__(self) -> _TE:
        item = await self._iter.__anext__()
        self._idx += 1
        return self._idx, item


class asyncenumerate(AsyncIterable[_TE]):
    """Imitates Python's :func:`enumerate` with async iterators.

    Args:
        iterable: The iterable to enumerate over.

    """

    def __init__(self, iterable: AsyncIterable[_T], start: int = 0) -> None:
        super().__init__()
        self._sub_iter = iterable
        self._start = start - 1

    def __aiter__(self) -> AsyncIterator[_TE]:
        sub_iter = self._sub_iter.__aiter__()
        return _AsyncEnumerateIterator(sub_iter, self._start)
