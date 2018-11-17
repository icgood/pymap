
import errno
from datetime import datetime
from email.message import EmailMessage
from mailbox import Maildir, MaildirMessage  # type: ignore
from typing import Tuple, Sequence, Dict, Optional, AsyncIterable, \
    Iterable, FrozenSet

from pymap.concurrent import Event, ReadWriteLock
from pymap.exceptions import MailboxNotFound, MailboxConflict, \
    MailboxHasChildren
from pymap.message import AppendMessage
from pymap.parsing.specials.flag import Flag
from pymap.selected import SelectedSet

from .flags import MaildirFlags
from .io import NoChanges
from .layout import MaildirLayout
from .subscriptions import Subscriptions
from .uidlist import Record, UidList
from ..mailbox import MailboxSnapshot, KeyValMessage, KeyValMailbox

__all__ = ['Message', 'MailboxSnapshot', 'Mailbox']

_Db = Dict[str, bytes]


class Message(KeyValMessage):

    def __init__(self, uid: int, contents: EmailMessage,
                 permanent_flags: Iterable[Flag],
                 internal_date: Optional[datetime],
                 recent: bool, maildir_flags: 'MaildirFlags'):
        super().__init__(uid, contents, permanent_flags, internal_date,
                         recent, maildir_flags)
        self.maildir_flags = maildir_flags

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
        msg_date = datetime.fromtimestamp(maildir_msg.get_date())
        msg_bytes = bytes(maildir_msg)
        return cls.parse(uid, msg_bytes, flag_set, msg_date, recent,
                         maildir_flags)


class Mailbox(KeyValMailbox[Message]):

    db_retry_count = 100
    db_retry_delay = 0.1
    filename_db = '.uid'
    filename_tmp_db = 'tmp.uid'

    def __init__(self, name: str, maildir: Maildir,
                 layout: MaildirLayout) -> None:
        self._name = name
        self._maildir = maildir
        self._layout = layout
        self._path = layout.get_path(name)
        self._uid_validity = 0
        self._next_uid = 0
        self._flags: Optional[MaildirFlags] = None
        self._messages_lock = ReadWriteLock.for_threading()
        self._folder_cache: Dict[str, 'Mailbox'] = {}
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
        return Message.parse(0, append_msg.message, append_msg.flag_set,
                             append_msg.when, True, self.maildir_flags)

    async def set_subscribed(self, name: str, subscribed: bool) -> None:
        async with Subscriptions.with_write(self._path) as subs:
            subs.set(name, subscribed)

    async def list_subscribed(self) -> Sequence[str]:
        async with Subscriptions.with_read(self._path) as subs:
            subscribed = frozenset(subs.subscribed)
        return [name for name in self._layout.list_folders()
                if name in subscribed]

    async def list_mailboxes(self) -> Sequence[str]:
        return self._layout.list_folders()

    async def get_mailbox(self, name: str,
                          try_create: bool = False) -> 'Mailbox':
        if name == 'INBOX':
            return await self.reset()
        try:
            maildir = self._layout.get_folder(name)
        except FileNotFoundError:
            raise MailboxNotFound(name, try_create)
        else:
            if name in self._folder_cache:
                mbx = self._folder_cache[name]
            else:
                mbx = Mailbox(name, maildir, self._layout)
                self._folder_cache[name] = mbx
            return await mbx.reset()

    async def add_mailbox(self, name: str) -> 'Mailbox':
        try:
            maildir = self._layout.add_folder(name)
        except FileExistsError:
            raise MailboxConflict(name)
        mbx = Mailbox(name, maildir, self._layout)
        self._folder_cache[name] = mbx
        return await mbx.reset()

    async def remove_mailbox(self, name: str) -> None:
        try:
            self._layout.remove_folder(name)
        except FileNotFoundError:
            raise MailboxNotFound(name)
        except OSError as exc:
            if exc.errno == errno.ENOTEMPTY:
                raise MailboxHasChildren(name) from exc
            raise exc

    async def rename_mailbox(self, before: str, after: str) -> 'Mailbox':
        if before == 'INBOX':
            before_mbx = await self.get_mailbox(before)
            after_mbx = await self.add_mailbox(after)
            async with before_mbx.messages_lock.read_lock():
                before_keys = sorted(before_mbx._maildir.keys())
                before_msgs = [before_mbx._maildir[key] for key in before_keys]
            async with after_mbx.messages_lock.write_lock():
                for maildir_msg in before_msgs:
                    after_mbx._maildir.add(maildir_msg)
            async with self.messages_lock.write_lock():
                self._maildir.clear()
            async with UidList.write_lock(self._path):
                UidList.delete(self._path)
        else:
            maildir = self._layout.rename_folder(before, after)
            after_mbx = Mailbox(after, maildir, self._layout)
        return await after_mbx.reset()

    async def add(self, message: Message, recent: bool = False) -> 'Message':
        recent = recent or message.recent
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

    async def delete(self, uid: int) -> None:
        async with UidList.with_read(self._path) as uidl:
            rec = uidl.get(uid)
            key = rec.filename.split(':', 1)[0]
        async with self.messages_lock.write_lock():
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
        folders = frozenset(self._layout.list_folders())
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
        async with Subscriptions.with_write(self._path) as subs:
            for folder in subs.subscribed:
                if folder not in folders:
                    subs.remove(folder)

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

    async def reset(self) -> 'Mailbox':
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
