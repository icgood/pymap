
from abc import abstractmethod
from typing import TypeVar, Tuple, Sequence, Optional, FrozenSet, AsyncIterable
from typing_extensions import Protocol

from pymap.concurrent import Event, ReadWriteLock
from pymap.mailbox import BaseMailbox
from pymap.message import AppendMessage, BaseLoadedMessage
from pymap.parsing.specials.flag import get_system_flags, Flag, Seen, Recent
from pymap.parsing.specials import SequenceSet
from pymap.selected import SelectedMailbox

from .util import asyncenumerate

__all__ = ['MailboxSnapshot', 'KeyValMessage', 'KeyValMailbox']

_T = TypeVar('_T', bound='KeyValMailbox')
_MT = TypeVar('_MT', bound='KeyValMessage')


class MailboxSnapshot(BaseMailbox):

    def __init__(self, name: str, readonly: bool, uid_validity: int,
                 permanent_flags: FrozenSet[Flag],
                 session_flags: FrozenSet[Flag],
                 exists: int, recent: int, unseen: int,
                 first_unseen: Optional[int], next_uid: int) -> None:
        super().__init__(name, permanent_flags, session_flags, readonly,
                         uid_validity)
        self._exists = exists
        self._recent = recent
        self._unseen = unseen
        self._first_unseen = first_unseen
        self._next_uid = next_uid

    @property
    def exists(self) -> int:
        return self._exists

    @property
    def recent(self) -> int:
        return self._recent

    @property
    def unseen(self) -> int:
        return self._unseen

    @property
    def first_unseen(self) -> Optional[int]:
        return self._first_unseen

    @property
    def next_uid(self) -> int:
        return self._next_uid


class KeyValMessage(BaseLoadedMessage):
    pass


class KeyValMailbox(Protocol[_MT]):

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @property
    @abstractmethod
    def uid_validity(self) -> int:
        ...

    @property
    @abstractmethod
    def messages_lock(self) -> ReadWriteLock:
        ...

    @property
    def permanent_flags(self) -> FrozenSet[Flag]:
        return get_system_flags() - {Recent}

    @property
    def session_flags(self) -> FrozenSet[Flag]:
        return frozenset({Recent})

    @property
    @abstractmethod
    def updated(self) -> Event:
        ...

    @property
    @abstractmethod
    def last_selected(self) -> Optional[SelectedMailbox]:
        ...

    @abstractmethod
    def new_selected(self, readonly: bool) -> SelectedMailbox:
        ...

    @abstractmethod
    def parse_message(self, append_msg: AppendMessage,
                      with_recent: bool) -> _MT:
        ...

    @abstractmethod
    async def set_subscribed(self, name: str, subscribed: bool) -> None:
        ...

    @abstractmethod
    async def list_subscribed(self) -> Sequence[str]:
        ...

    @abstractmethod
    async def list_mailboxes(self) -> Sequence[str]:
        ...

    @abstractmethod
    async def get_mailbox(self: _T, name: str) -> _T:
        ...

    @abstractmethod
    async def add_mailbox(self: _T, name: str) -> _T:
        ...

    @abstractmethod
    async def remove_mailbox(self, name: str) -> None:
        ...

    @abstractmethod
    async def rename_mailbox(self: _T, before: str, after: str) -> _T:
        ...

    @abstractmethod
    async def get_max_uid(self) -> int:
        ...

    @abstractmethod
    async def add(self, message: _MT) -> _MT:
        ...

    @abstractmethod
    async def get(self, uid: int) -> Optional[_MT]:
        ...

    @abstractmethod
    async def delete(self, uid: int) -> None:
        ...

    @abstractmethod
    async def save_flags(self, *messages: _MT) -> None:
        ...

    @abstractmethod
    async def get_count(self) -> int:
        ...

    @abstractmethod
    async def cleanup(self) -> None:
        ...

    @abstractmethod
    def uids(self) -> AsyncIterable[int]:
        ...

    @abstractmethod
    def messages(self) -> AsyncIterable[_MT]:
        ...

    @abstractmethod
    def items(self) -> AsyncIterable[Tuple[int, _MT]]:
        ...

    async def find(self, seq_set: SequenceSet, selected: SelectedMailbox) \
            -> AsyncIterable[Tuple[int, _MT]]:
        for seq, uid in selected.iter_set(seq_set):
            msg = await self.get(uid)
            if msg is not None:
                yield (seq, msg)

    async def snapshot(self) -> MailboxSnapshot:
        readonly = False
        exists = await self.get_count()
        recent = 0
        unseen = 0
        first_unseen: Optional[int] = None
        async for seq, msg in asyncenumerate(self.messages(), 1):
            if Recent in msg.permanent_flags:
                recent += 1
            if Seen not in msg.permanent_flags:
                unseen += 1
                if first_unseen is None:
                    first_unseen = seq
        next_uid = await self.get_max_uid() + 1
        return MailboxSnapshot(self.name, readonly, self.uid_validity,
                               self.permanent_flags, self.session_flags,
                               exists, recent, unseen, first_unseen,
                               next_uid)
