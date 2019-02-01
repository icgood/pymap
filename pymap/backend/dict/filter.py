
from typing import Optional, Tuple, Sequence, Dict

from pymap.filter import EntryPointFilterSet

__all__ = ['FilterSet']


class FilterSet(EntryPointFilterSet[bytes]):

    def __init__(self) -> None:
        super().__init__('sieve')
        self._filters: Dict[str, bytes] = {}
        self._active: Optional[str] = None

    async def put(self, name: str, value: bytes) -> None:
        self._filters[name] = value

    async def delete(self, name: str) -> None:
        if name not in self._filters:
            raise KeyError(name)
        elif name == self._active:
            raise ValueError(name)
        del self._filters[name]

    async def rename(self, before_name: str, after_name: str) -> None:
        if before_name not in self._filters:
            raise KeyError(before_name)
        elif after_name in self._filters:
            raise KeyError(after_name)
        self._filters[after_name] = self._filters[before_name]
        del self._filters[before_name]
        if self._active == before_name:
            self._active = after_name

    async def set_active(self, name: Optional[str]) -> None:
        if name is None:
            self._active = None
        elif name not in self._filters:
            raise KeyError(name)
        else:
            self._active = name

    async def get(self, name: str) -> bytes:
        return self._filters[name]

    async def get_active(self) -> Optional[bytes]:
        if self._active is None:
            return None
        else:
            return self._filters[self._active]

    async def get_all(self) -> Tuple[Optional[str], Sequence[str]]:
        return self._active, list(self._filters.keys())
