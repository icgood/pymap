
from abc import abstractmethod
from datetime import datetime
from email.message import EmailMessage
from typing import TypeVar, Tuple, Sequence, Optional, FrozenSet, \
    AsyncIterable, Iterable
from typing_extensions import Protocol

from pymap.concurrent import ReadWriteLock
from pymap.mailbox import MailboxSnapshot
from pymap.message import AppendMessage, BaseLoadedMessage
from pymap.parsing.specials.flag import get_system_flags, Flag, Seen, Recent
from pymap.parsing.specials import SequenceSet
from pymap.selected import SelectedSet, SelectedMailbox

from .util import asyncenumerate

__all__ = ['KeyValMessage', 'KeyValMailbox']

_MailboxT = TypeVar('_MailboxT', bound='KeyValMailbox')
_MessageT = TypeVar('_MessageT', bound='KeyValMessage')


class KeyValMessage(BaseLoadedMessage):

    def __init__(self, uid: int, contents: EmailMessage,
                 permanent_flags: Iterable[Flag],
                 internal_date: Optional[datetime],
                 recent: bool, *args, **kwargs):
        super().__init__(uid, contents, permanent_flags, internal_date,
                         recent, *args, **kwargs)
        self.recent = recent


class KeyValMailbox(Protocol[_MessageT]):

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @property
    @abstractmethod
    def readonly(self) -> bool:
        ...

    @property
    @abstractmethod
    def uid_validity(self) -> int:
        ...

    @property
    @abstractmethod
    def next_uid(self) -> int:
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
    def selected_set(self) -> SelectedSet:
        ...

    @abstractmethod
    def parse_message(self, append_msg: AppendMessage) -> _MessageT:
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
    async def get_mailbox(self: _MailboxT, name: str,
                          try_create: bool = False) -> _MailboxT:
        ...

    @abstractmethod
    async def add_mailbox(self: _MailboxT, name: str) -> _MailboxT:
        ...

    @abstractmethod
    async def remove_mailbox(self, name: str) -> None:
        ...

    @abstractmethod
    async def rename_mailbox(self: _MailboxT, before: str,
                             after: str) -> _MailboxT:
        ...

    @abstractmethod
    async def add(self, message: _MessageT, recent: bool = False) -> _MessageT:
        ...

    @abstractmethod
    async def get(self, uid: int) -> Optional[_MessageT]:
        ...

    @abstractmethod
    async def delete(self, uid: int) -> None:
        ...

    @abstractmethod
    async def save_flags(self, *messages: _MessageT) -> None:
        ...

    @abstractmethod
    async def cleanup(self) -> None:
        ...

    @abstractmethod
    def uids(self) -> AsyncIterable[int]:
        ...

    @abstractmethod
    def messages(self) -> AsyncIterable[_MessageT]:
        ...

    @abstractmethod
    def items(self) -> AsyncIterable[Tuple[int, _MessageT]]:
        ...

    async def find(self, seq_set: SequenceSet, selected: SelectedMailbox) \
            -> AsyncIterable[Tuple[int, _MessageT]]:
        for seq, uid in selected.snapshot.iter_set(seq_set):
            msg = await self.get(uid)
            if msg is not None:
                yield (seq, msg)

    async def snapshot(self) -> MailboxSnapshot:
        exists = 0
        recent = 0
        unseen = 0
        first_unseen: Optional[int] = None
        async for seq, msg in asyncenumerate(self.messages(), 1):
            exists += 1
            if msg.recent:
                recent += 1
            if Seen not in msg.permanent_flags:
                unseen += 1
                if first_unseen is None:
                    first_unseen = seq
        return MailboxSnapshot(self.name, self.readonly, self.uid_validity,
                               self.permanent_flags, self.session_flags,
                               exists, recent, unseen, first_unseen,
                               self.next_uid)
