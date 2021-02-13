
from collections.abc import Iterable, Sequence
from typing import Union

__all__ = ['whitespace', 'find_any', 'get_raw']

whitespace = frozenset(b' \t\n\r\x0b\f')

_Line = tuple[int, int, int]
_Lines = Sequence[_Line]


def find_any(data: Union[bytes, memoryview], end_marker: frozenset[int],
             start: int, end: int, inverse: bool, reverse: bool) -> int:
    if reverse:
        range_iter: Iterable[int] = reversed(range(start, end))
    else:
        range_iter = range(start, end)
    for i in range_iter:
        match = (data[i] in end_marker)
        if (not match and not inverse) or (match and inverse):
            if reverse:
                return i + 1
            else:
                return i
    return -1


def get_raw(view: memoryview, *lines: _Lines) -> memoryview:
    try:
        start = lines[0][0][0]
    except IndexError:
        start = 0
    try:
        end = lines[-1][-1][2]
    except IndexError:
        end = -1
    return view[start:end]
