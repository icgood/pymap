
from collections import OrderedDict
from typing import Tuple, Sequence, Dict, Optional, AsyncIterable
from weakref import WeakSet

from pymap.concurrent import Event, ReadWriteLock
from pymap.exceptions import MailboxNotFound, MailboxConflict
from pymap.selected import SelectedMailbox

from ..mailbox import MailboxSnapshot, KeyValMessage, KeyValMailbox

__all__ = ['Message', 'Mailbox']


class Message(KeyValMessage):
    """Implementation of :class:`~pymap.keyval.mailbox.KeyValMessage` for the
    dict backend.

    """
    pass


class Mailbox(KeyValMailbox[Message]):
    """Implementation of :class:`~pymap.keyval.mailbox.KeyValMailbox` for the
    dict backend.

    """

    def __init__(self, name: str) -> None:
        self._name = name
        self._subscribed: Dict[str, bool] = {}
        self._messages_lock = ReadWriteLock.for_asyncio()
        self._children: Dict[str, 'Mailbox'] = OrderedDict()
        self._children_lock = ReadWriteLock.for_asyncio()
        self._last_selected: WeakSet[SelectedMailbox] = WeakSet()
        self._updated = Event.for_asyncio()
        self._reset_messages()

    def _reset_messages(self) -> None:
        self._uid_validity = MailboxSnapshot.new_uid_validity()
        self._max_uid = 100
        self._messages: Dict[int, Message] = OrderedDict()

    @property
    def name(self) -> str:
        return self._name

    @property
    def uid_validity(self) -> int:
        return self._uid_validity

    @property
    def messages_lock(self) -> ReadWriteLock:
        return self._messages_lock

    @property
    def updated(self) -> Event:
        return self._updated

    @property
    def last_selected(self) -> Optional[SelectedMailbox]:
        for selected in self._last_selected:
            return selected
        return None

    def _update_last_selected(self, orig: SelectedMailbox,
                              forked: SelectedMailbox) -> None:
        self._last_selected.remove(orig)
        self._last_selected.add(forked)

    def new_selected(self, readonly: bool) -> SelectedMailbox:
        selected = SelectedMailbox(self.name, readonly,
                                   on_fork=self._update_last_selected)
        self._last_selected.add(selected)
        return selected

    async def set_subscribed(self, name: str, subscribed: bool) -> None:
        async with self._children_lock.write_lock():
            self._subscribed[name] = subscribed

    async def list_subscribed(self) -> Sequence[str]:
        async with self._children_lock.read_lock():
            return [child for child in self._children.keys()
                    if self._subscribed.get(child)]

    async def list_mailboxes(self) -> Sequence[str]:
        async with self._children_lock.read_lock():
            return list(self._children.keys())

    async def get_mailbox(self, name: str) -> 'Mailbox':
        if name.upper() == 'INBOX':
            return self
        async with self._children_lock.read_lock():
            if name not in self._children:
                raise MailboxNotFound(name)
            return self._children[name]

    async def add_mailbox(self, name: str) -> 'Mailbox':
        async with self._children_lock.read_lock():
            if name in self._children:
                raise MailboxConflict(name)
        async with self._children_lock.write_lock():
            self._children[name] = ret = Mailbox(name)
        return ret

    async def remove_mailbox(self, name: str) -> None:
        async with self._children_lock.read_lock():
            if name not in self._children:
                raise MailboxNotFound(name)
        async with self._children_lock.write_lock():
            del self._children[name]

    async def rename_mailbox(self, before: str, after: str) -> 'Mailbox':
        async with self._children_lock.read_lock():
            if before != 'INBOX' and before not in self._children:
                raise MailboxNotFound(before)
            elif after in self._children:
                raise MailboxConflict(after)
        if before == 'INBOX':
            async with self._children_lock.write_lock():
                self._children[after] = ret = Mailbox(after)
                ret._uid_validity = self._uid_validity
                ret._max_uid = self._max_uid
                ret._messages = self._messages
                self._reset_messages()
                return ret
        else:
            async with self._children_lock.write_lock():
                self._children[after] = self._children[before]
                del self._children[before]
                return self._children[after]

    async def get_max_uid(self) -> int:
        async with self.messages_lock.read_lock():
            return self._max_uid

    async def add(self, message: Message) -> Message:
        async with self.messages_lock.write_lock():
            self._max_uid += 1
            message = message.copy(self._max_uid)
            self._messages[message.uid] = message
            return message

    async def get(self, uid: int) -> Message:
        async with self.messages_lock.read_lock():
            return self._messages[uid]

    async def delete(self, uid: int) -> None:
        async with self.messages_lock.write_lock():
            del self._messages[uid]

    async def save_flags(self, *messages: Message) -> None:
        pass

    async def get_count(self) -> int:
        async with self.messages_lock.read_lock():
            return len(self._messages)

    async def cleanup(self) -> None:
        pass

    async def uids(self) -> AsyncIterable[int]:
        async with self.messages_lock.read_lock():
            for key in self._messages.keys():
                yield key

    async def messages(self) -> AsyncIterable[Message]:
        async with self.messages_lock.read_lock():
            for msg in self._messages.values():
                yield msg

    async def items(self) -> AsyncIterable[Tuple[int, Message]]:
        async with self.messages_lock.read_lock():
            for key, msg in self._messages.items():
                yield (key, msg)
