
from collections import OrderedDict
from io import BytesIO
from typing import Tuple, Sequence, Dict, Optional, AsyncIterable

from pymap.concurrent import ReadWriteLock
from pymap.exceptions import MailboxNotFound, MailboxConflict
from pymap.mailbox import MailboxSnapshot
from pymap.message import AppendMessage
from pymap.selected import SelectedSet

from ..mailbox import LoadedMessage, MailboxDataInterface, MailboxSetInterface

__all__ = ['Message', 'MailboxData', 'MailboxSet']


class Message(LoadedMessage):
    pass


class MailboxData(MailboxDataInterface[Message, Message]):
    """Implementation of :class:`~pymap.backend.mailbox.MailboxDataInterface`
    for the dict backend.

    """

    def __init__(self, name: str) -> None:
        self._name = name
        self._readonly = False
        self._messages_lock = ReadWriteLock.for_asyncio()
        self._selected_set = SelectedSet()
        self._reset_messages()

    def _reset_messages(self) -> None:
        self._uid_validity = MailboxSnapshot.new_uid_validity()
        self._max_uid = 100
        self._messages: Dict[int, Message] = OrderedDict()

    @property
    def name(self) -> str:
        return self._name

    @property
    def readonly(self) -> bool:
        return self._readonly

    @property
    def uid_validity(self) -> int:
        return self._uid_validity

    @property
    def next_uid(self) -> int:
        return self._max_uid + 1

    @property
    def messages_lock(self) -> ReadWriteLock:
        return self._messages_lock

    @property
    def selected_set(self) -> SelectedSet:
        return self._selected_set

    def parse_message(self, append_msg: AppendMessage) -> Message:
        msg_data = BytesIO(append_msg.message)
        return Message.parse(0, msg_data, append_msg.flag_set,
                             append_msg.when, recent=True)

    async def add(self, message: Message, recent: bool = False) -> Message:
        async with self.messages_lock.write_lock():
            self._max_uid += 1
            msg_copy = message.copy(self._max_uid)
            msg_copy.recent = recent or message.recent
            self._messages[msg_copy.uid] = msg_copy
            return msg_copy

    async def get(self, uid: int) -> Optional[Message]:
        async with self.messages_lock.read_lock():
            return self._messages.get(uid)

    async def delete(self, uid: int) -> None:
        async with self.messages_lock.write_lock():
            del self._messages[uid]

    async def save_flags(self, *messages: Message) -> None:
        pass

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


class MailboxSet(MailboxSetInterface[MailboxData]):
    """Implementation of :class:`~pymap.backend.mailbox.MailboxSetInterface`
    for the dict backend.

    """

    def __init__(self) -> None:
        super().__init__()
        self._inbox = MailboxData('INBOX')
        self._set: Dict[str, 'MailboxData'] = OrderedDict()
        self._set_lock = ReadWriteLock.for_asyncio()
        self._subscribed: Dict[str, bool] = {}

    @property
    def inbox(self) -> MailboxData:
        return self._inbox

    @property
    def delimiter(self) -> str:
        return '.'

    async def set_subscribed(self, name: str, subscribed: bool) -> None:
        async with self._set_lock.write_lock():
            self._subscribed[name] = subscribed

    async def list_subscribed(self) -> Sequence[str]:
        async with self._set_lock.read_lock():
            return [child for child in self._set.keys()
                    if self._subscribed.get(child)]

    async def list_mailboxes(self) -> Sequence[str]:
        async with self._set_lock.read_lock():
            return list(self._set.keys())

    async def get_mailbox(self, name: str,
                          try_create: bool = False) -> 'MailboxData':
        if name.upper() == 'INBOX':
            return self.inbox
        async with self._set_lock.read_lock():
            if name not in self._set:
                raise MailboxNotFound(name, try_create)
            return self._set[name]

    async def add_mailbox(self, name: str) -> 'MailboxData':
        async with self._set_lock.read_lock():
            if name in self._set:
                raise MailboxConflict(name)
        async with self._set_lock.write_lock():
            self._set[name] = ret = MailboxData(name)
        return ret

    async def delete_mailbox(self, name: str) -> None:
        async with self._set_lock.read_lock():
            if name not in self._set:
                raise MailboxNotFound(name)
        async with self._set_lock.write_lock():
            del self._set[name]

    async def rename_mailbox(self, before: str, after: str) -> 'MailboxData':
        async with self._set_lock.read_lock():
            if before != 'INBOX' and before not in self._set:
                raise MailboxNotFound(before)
            elif after in self._set:
                raise MailboxConflict(after)
        if before == 'INBOX':
            async with self._set_lock.write_lock():
                self._set[after] = ret = MailboxData(after)
                ret._uid_validity = self.inbox._uid_validity
                ret._max_uid = self.inbox._max_uid
                ret._messages = self.inbox._messages
                self.inbox._reset_messages()
                return ret
        else:
            async with self._set_lock.write_lock():
                self._set[after] = self._set[before]
                del self._set[before]
                return self._set[after]
