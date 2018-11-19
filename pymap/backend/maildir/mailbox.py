
import errno
from datetime import datetime
from io import BytesIO
from mailbox import Maildir, MaildirMessage  # type: ignore
from typing import Tuple, Sequence, Dict, Optional, AsyncIterable, FrozenSet

from pymap.concurrent import Event, ReadWriteLock
from pymap.exceptions import MailboxNotFound, MailboxConflict, \
    MailboxHasChildren
from pymap.message import AppendMessage
from pymap.parsing.specials import Flag
from pymap.selected import SelectedSet

from .flags import MaildirFlags
from .io import NoChanges
from .layout import MaildirLayout
from .subscriptions import Subscriptions
from .uidlist import Record, UidList
from ..mailbox import LoadedMessage, MailboxDataInterface, MailboxSetInterface

__all__ = ['Message', 'MailboxData', 'MailboxSet']

_Db = Dict[str, bytes]


class Message(LoadedMessage):

    @property
    def maildir_flags(self) -> MaildirFlags:
        return self._kwargs['maildir_flags']

    @property
    def maildir_msg(self) -> MaildirMessage:
        flag_str = self.maildir_flags.to_maildir(self.permanent_flags)
        msg_bytes = self.get_body(binary=True)
        maildir_msg = MaildirMessage(msg_bytes)
        maildir_msg.set_flags(flag_str)
        maildir_msg.set_subdir('new' if self.recent else 'cur')
        if self.internal_date is not None:
            maildir_msg.set_date(self.internal_date.timestamp())
        return maildir_msg

    @classmethod
    def from_maildir(cls, uid: int, maildir_msg: MaildirMessage,
                     maildir_flags: 'MaildirFlags') -> 'Message':
        flag_set = maildir_flags.from_maildir(maildir_msg.get_flags())
        recent = maildir_msg.get_subdir() == 'new'
        msg_dt = datetime.fromtimestamp(maildir_msg.get_date())
        msg_data = BytesIO(bytes(maildir_msg))
        return cls.parse(uid, msg_data, flag_set, msg_dt, recent=recent,
                         maildir_flags=maildir_flags)


class MailboxData(MailboxDataInterface[Message, Message]):

    db_retry_count = 100
    db_retry_delay = 0.1
    filename_db = '.uid'
    filename_tmp_db = 'tmp.uid'

    def __init__(self, name: str, maildir: Maildir, path: str) -> None:
        self._name = name
        self._maildir = maildir
        self._path = path
        self._uid_validity = 0
        self._next_uid = 0
        self._flags: Optional[MaildirFlags] = None
        self._messages_lock = ReadWriteLock.for_threading()
        self._selected_set = SelectedSet(Event.for_threading())

    @property
    def name(self) -> str:
        return self._name

    @property
    def readonly(self) -> bool:
        return False

    @property
    def uid_validity(self) -> int:
        return self._uid_validity

    @property
    def next_uid(self) -> int:
        return self._next_uid

    @property
    def maildir_flags(self) -> MaildirFlags:
        if self._flags is not None:
            return self._flags
        self._flags = flags = MaildirFlags.file_read(self._path)
        return flags

    @property
    def permanent_flags(self) -> FrozenSet[Flag]:
        return self.maildir_flags.permanent_flags

    @property
    def messages_lock(self) -> ReadWriteLock:
        return self._messages_lock

    @property
    def selected_set(self) -> SelectedSet:
        return self._selected_set

    def parse_message(self, append_msg: AppendMessage) -> Message:
        msg_data = BytesIO(append_msg.message)
        return Message.parse(0, msg_data, append_msg.flag_set,
                             append_msg.when, recent=True,
                             maildir_flags=self.maildir_flags)

    async def add(self, message: Message, recent: bool = False) -> 'Message':
        async with self.messages_lock.write_lock():
            maildir_msg = message.maildir_msg
            if recent:
                maildir_msg.set_subdir('new')
            key = self._maildir.add(maildir_msg)
            filename = key + ':' + maildir_msg.get_info()
        async with UidList.with_write(self._path) as uidl:
            new_rec = Record(uidl.next_uid, {}, filename)
            uidl.next_uid += 1
            uidl.set(new_rec)
        msg_copy = message.copy(new_rec.uid)
        msg_copy.recent = recent
        return msg_copy

    async def get(self, uid: int) -> Optional[Message]:
        async with UidList.with_read(self._path) as uidl:
            rec = uidl.get(uid)
            key = rec.filename.split(':', 1)[0]
        async with self.messages_lock.read_lock():
            try:
                maildir_msg = self._maildir[key]
            except (KeyError, FileNotFoundError):
                return None
            return Message.from_maildir(uid, maildir_msg, self.maildir_flags)

    async def delete(self, *uids: int) -> None:
        keys: Dict[int, str] = {}
        async with UidList.with_read(self._path) as uidl:
            for uid in uids:
                try:
                    rec = uidl.get(uid)
                    keys[uid] = rec.filename.split(':', 1)[0]
                except KeyError:
                    pass
        async with self.messages_lock.write_lock():
            for uid, key in keys.items():
                try:
                    del self._maildir[key]
                except (KeyError, FileNotFoundError):
                    pass

    async def save_flags(self, *messages: Message) -> None:
        keys: Dict[int, str] = {}
        async with UidList.with_read(self._path) as uidl:
            for message in messages:
                rec = uidl.get(message.uid)
                keys[message.uid] = rec.filename.split(':', 1)[0]
        async with self.messages_lock.write_lock():
            for message in messages:
                key = keys[message.uid]
                flag_set = message.permanent_flags
                flag_str = self.maildir_flags.to_maildir(flag_set)
                try:
                    maildir_msg = self._maildir[key]
                except (KeyError, FileNotFoundError):
                    pass
                else:
                    maildir_msg.set_flags(flag_str)
                    maildir_msg.set_subdir('new' if message.recent else 'cur')
                    self._maildir[key] = maildir_msg

    async def cleanup(self) -> None:
        self._maildir.clean()
        keys = await self._get_keys()
        async with UidList.with_write(self._path) as uidl:
            for rec in list(uidl.records):
                key = rec.filename.split(':', 1)[0]
                info = keys.get(key)
                if info is None:
                    uidl.remove(rec.uid)
                else:
                    filename = key + ':' + info
                    new_rec = Record(rec.uid, rec.fields, filename)
                    uidl.set(new_rec)

    async def uids(self) -> AsyncIterable[int]:
        uids: Dict[int, str] = {}
        async with UidList.with_read(self._path) as uidl:
            for rec in uidl.records:
                key = rec.filename.split(':', 1)[0]
                uids[rec.uid] = key
        async with self.messages_lock.read_lock():
            for uid, key in uids.items():
                if key in self._maildir:
                    yield uid

    async def messages(self) -> AsyncIterable[Message]:
        uids: Dict[int, str] = {}
        async with UidList.with_read(self._path) as uidl:
            for rec in uidl.records:
                key = rec.filename.split(':', 1)[0]
                uids[rec.uid] = key
        async with self.messages_lock.read_lock():
            for uid, key in uids.items():
                try:
                    maildir_msg = self._maildir[key]
                except (KeyError, FileNotFoundError):
                    pass
                else:
                    yield Message.from_maildir(
                        uid, maildir_msg, self.maildir_flags)

    async def items(self) -> AsyncIterable[Tuple[int, Message]]:
        uids: Dict[int, str] = {}
        async with UidList.with_read(self._path) as uidl:
            for rec in uidl.records:
                key = rec.filename.split(':', 1)[0]
                uids[rec.uid] = key
        async with self.messages_lock.read_lock():
            for uid, key in uids.items():
                try:
                    maildir_msg = self._maildir[key]
                except (KeyError, FileNotFoundError):
                    pass
                else:
                    yield uid, Message.from_maildir(
                        uid, maildir_msg, self.maildir_flags)

    async def reset(self) -> 'MailboxData':
        keys = await self._get_keys()
        async with UidList.with_write(self._path) as uidl:
            for rec in uidl.records:
                key = rec.filename.split(':', 1)[0]
                keys.pop(key, None)
            if not keys:
                raise NoChanges()
            for key, info in keys.items():
                filename = key + ':' + info
                new_rec = Record(uidl.next_uid, {}, filename)
                uidl.next_uid += 1
                uidl.set(new_rec)
        self._uid_validity = uidl.uid_validity
        self._next_uid = uidl.next_uid
        return self

    async def _get_keys(self) -> Dict[str, str]:
        keys: Dict[str, str] = {}
        async with self.messages_lock.read_lock():
            for key in self._maildir.keys():
                try:
                    msg = self._maildir[key]
                except (KeyError, FileNotFoundError):
                    pass
                else:
                    keys[key] = msg.get_info()
        return keys


class MailboxSet(MailboxSetInterface[MailboxData]):

    def __init__(self, maildir: Maildir, layout: MaildirLayout) -> None:
        super().__init__()
        self._layout = layout
        self._inbox = MailboxData('INBOX', maildir, layout.path)
        self._cache: Dict[str, 'MailboxData'] = {}

    @property
    def inbox(self) -> MailboxData:
        return self._inbox

    @property
    def delimiter(self) -> str:
        return '/'

    async def set_subscribed(self, name: str, subscribed: bool) -> None:
        async with Subscriptions.with_write(self.inbox._path) as subs:
            subs.set(name, subscribed)

    async def list_subscribed(self) -> Sequence[str]:
        async with Subscriptions.with_read(self.inbox._path) as subs:
            subscribed = frozenset(subs.subscribed)
        return [name for name in self._layout.list_folders(self.delimiter)
                if name in subscribed]

    async def list_mailboxes(self) -> Sequence[str]:
        return self._layout.list_folders(self.delimiter)

    async def get_mailbox(self, name: str,
                          try_create: bool = False) -> 'MailboxData':
        if name == 'INBOX':
            return await self.inbox.reset()
        try:
            maildir = self._layout.get_folder(name, self.delimiter)
        except FileNotFoundError:
            raise MailboxNotFound(name, try_create)
        else:
            if name in self._cache:
                mbx = self._cache[name]
            else:
                path = self._layout.get_path(name, self.delimiter)
                mbx = MailboxData(name, maildir, path)
                self._cache[name] = mbx
            return await mbx.reset()

    async def add_mailbox(self, name: str) -> 'MailboxData':
        try:
            maildir = self._layout.add_folder(name, self.delimiter)
        except FileExistsError:
            raise MailboxConflict(name)
        path = self._layout.get_path(name, self.delimiter)
        mbx = MailboxData(name, maildir, path)
        self._cache[name] = mbx
        return await mbx.reset()

    async def delete_mailbox(self, name: str) -> None:
        try:
            self._layout.remove_folder(name, self.delimiter)
        except FileNotFoundError:
            raise MailboxNotFound(name)
        except OSError as exc:
            if exc.errno == errno.ENOTEMPTY:
                raise MailboxHasChildren(name) from exc
            raise exc

    async def rename_mailbox(self, before: str, after: str) -> 'MailboxData':
        if before == 'INBOX':
            before_mbx = await self.get_mailbox(before)
            after_mbx = await self.add_mailbox(after)
            async with before_mbx.messages_lock.read_lock():
                before_keys = sorted(before_mbx._maildir.keys())
                before_msgs = [before_mbx._maildir[key] for key in before_keys]
            async with after_mbx.messages_lock.write_lock():
                for maildir_msg in before_msgs:
                    after_mbx._maildir.add(maildir_msg)
            async with self.inbox.messages_lock.write_lock():
                self.inbox._maildir.clear()
            async with UidList.write_lock(self.inbox._path):
                UidList.delete(self.inbox._path)
        else:
            maildir = self._layout.rename_folder(before, after, self.delimiter)
            after_path = self._layout.get_path(after, self.delimiter)
            after_mbx = MailboxData(after, maildir, after_path)
        return await after_mbx.reset()
