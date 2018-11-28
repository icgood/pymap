
import errno
import os
import os.path
from datetime import datetime
from io import BytesIO
from mailbox import Maildir as _Maildir, MaildirMessage  # type: ignore
from typing import Tuple, Sequence, Dict, Optional, FrozenSet, \
    Iterable, AsyncIterable

from pymap.concurrent import Event, ReadWriteLock
from pymap.exceptions import MailboxNotFound, MailboxConflict, \
    MailboxHasChildren
from pymap.message import AppendMessage
from pymap.parsing.specials import Flag, FetchRequirement
from pymap.selected import SelectedSet, SelectedMailbox

from .flags import MaildirFlags
from .io import NoChanges
from .layout import MaildirLayout
from .subscriptions import Subscriptions
from .uidlist import Record, UidList
from ..mailbox import MailboxDataInterface, MailboxSetInterface, \
    Message as _Message

__all__ = ['Maildir', 'Message', 'MailboxData', 'MailboxSet']


class Maildir(_Maildir):

    def claim_new(self) -> Iterable[str]:
        """Checks for messages in the ``new`` subdirectory, moving them to
        ``cur`` and returning their keys.

        """
        new_subdir = self._paths['new']
        cur_subdir = self._paths['cur']
        for name in os.listdir(new_subdir):
            new_path = os.path.join(new_subdir, name)
            cur_path = os.path.join(cur_subdir, name)
            try:
                os.rename(new_path, cur_path)
            except FileNotFoundError:
                pass
            else:
                yield name.rsplit(self.colon, 1)[0]

    def get_message_metadata(self, key: str) -> MaildirMessage:
        """Like :meth:`~mailbox.Maildir.get_message` but the message contents
        are not read from disk.

        """
        msg = MaildirMessage()
        subpath = self._lookup(key)
        subdir, name = os.path.split(subpath)
        msg.set_subdir(subdir)
        if self.colon in name:
            msg.set_info(name.rsplit(self.colon, 1)[-1])
        msg.set_date(os.path.getmtime(os.path.join(self._path, subpath)))
        return msg

    def update_metadata(self, key: str, msg: MaildirMessage) -> None:
        """Uses :func:`os.rename` to atomically update the message filename
        based on :meth:`~mailbox.MaildirMessage.get_info`.

        """
        subpath = self._lookup(key)
        subdir, name = os.path.split(subpath)
        new_subdir = msg.get_subdir()
        new_name = key + self.colon + msg.get_info()
        if subdir != new_subdir:
            raise ValueError('Message subdir may not be updated')
        elif name != new_name:
            new_subpath = os.path.join(msg.get_subdir(), new_name)
            old_path = os.path.join(self._path, subpath)
            new_path = os.path.join(self._path, new_subpath)
            os.rename(old_path, new_path)
            self._toc[key] = new_subpath


class Message(_Message):

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
                     maildir_flags: 'MaildirFlags',
                     metadata_only: bool) -> 'Message':
        flag_set = maildir_flags.from_maildir(maildir_msg.get_flags())
        recent = maildir_msg.get_subdir() == 'new'
        msg_dt = datetime.fromtimestamp(maildir_msg.get_date())
        if metadata_only:
            return cls(uid, flag_set, msg_dt, recent=recent,
                       maildir_flags=maildir_flags)
        else:
            msg_data = BytesIO(bytes(maildir_msg))
            return cls.parse(uid, msg_data, flag_set, msg_dt, recent=recent,
                             maildir_flags=maildir_flags)


class MailboxData(MailboxDataInterface[Message]):

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

    async def get(self, uid: int,
                  requirement: FetchRequirement = FetchRequirement.METADATA) \
            -> Optional[Message]:
        async with UidList.with_read(self._path) as uidl:
            next_uid = uidl.next_uid
            try:
                key = uidl.get(uid).key
            except KeyError:
                return None
        metadata_only = (requirement == FetchRequirement.METADATA)
        async with self.messages_lock.read_lock():
            try:
                if metadata_only:
                    maildir_msg = self._maildir.get_message_metadata(key)
                else:
                    maildir_msg = self._maildir.get_message(key)
            except (KeyError, FileNotFoundError):
                if uid < next_uid:
                    return Message(uid, expunged=True)
                else:
                    return None
            return Message.from_maildir(uid, maildir_msg, self.maildir_flags,
                                        metadata_only)

    async def delete(self, uids: Iterable[int]) -> None:
        async with UidList.with_read(self._path) as uidl:
            records = uidl.get_all(uids)
        async with self.messages_lock.write_lock():
            for uid, rec in records.items():
                try:
                    self._maildir.remove(rec.key)
                except (KeyError, FileNotFoundError):
                    pass

    async def claim_recent(self, selected: SelectedMailbox) -> None:
        async with self.messages_lock.write_lock():
            keys = self._maildir.claim_new()
        async with UidList.with_read(self._path) as uidl:
            for rec in uidl.records:
                if rec.key in keys:
                    selected.session_flags.add_recent(rec.uid)

    async def save_flags(self, messages: Iterable[Message]) -> None:
        msgs_map = {msg.uid: msg for msg in messages}
        async with UidList.with_read(self._path) as uidl:
            records = uidl.get_all(msgs_map.keys())
        async with self.messages_lock.write_lock():
            for uid, rec in records.items():
                key = rec.key
                message = msgs_map[uid]
                flag_set = message.permanent_flags
                flag_str = self.maildir_flags.to_maildir(flag_set)
                try:
                    maildir_msg = self._maildir.get_message_metadata(key)
                except (KeyError, FileNotFoundError):
                    continue
                maildir_msg.set_flags(flag_str)
                maildir_msg.set_subdir('new' if message.recent else 'cur')
                try:
                    self._maildir.update_metadata(key, maildir_msg)
                except (KeyError, FileNotFoundError):
                    pass

    async def cleanup(self) -> None:
        self._maildir.clean()
        keys = await self._get_keys()
        async with UidList.with_write(self._path) as uidl:
            for rec in list(uidl.records):
                key = rec.key
                info = keys.get(key)
                if info is None:
                    uidl.remove(rec.uid)
                else:
                    filename = key + ':' + info
                    new_rec = Record(rec.uid, rec.fields, filename)
                    uidl.set(new_rec)

    async def uids(self) -> AsyncIterable[int]:
        async with UidList.with_read(self._path) as uidl:
            uids = {rec.uid: rec.key for rec in uidl.records}
        async with self.messages_lock.read_lock():
            keys = frozenset(self._maildir.keys())
        for uid, key in uids.items():
            if key in keys:
                yield uid

    async def messages(self) -> AsyncIterable[Message]:
        async with UidList.with_read(self._path) as uidl:
            uids = {rec.uid: rec.key for rec in uidl.records}
        async with self.messages_lock.read_lock():
            for uid, key in uids.items():
                try:
                    maildir_msg = self._maildir.get_message_metadata(key)
                except (KeyError, FileNotFoundError):
                    pass
                else:
                    yield Message.from_maildir(
                        uid, maildir_msg, self.maildir_flags, True)

    async def items(self) -> AsyncIterable[Tuple[int, Message]]:
        async with UidList.with_read(self._path) as uidl:
            uids = {rec.uid: rec.key for rec in uidl.records}
        async with self.messages_lock.read_lock():
            for uid, key in uids.items():
                try:
                    maildir_msg = self._maildir.get_message_metadata(key)
                except (KeyError, FileNotFoundError):
                    pass
                else:
                    yield uid, Message.from_maildir(
                        uid, maildir_msg, self.maildir_flags, True)

    async def reset(self) -> 'MailboxData':
        keys = await self._get_keys()
        async with UidList.with_write(self._path) as uidl:
            for rec in uidl.records:
                keys.pop(rec.key, None)
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
                    msg = self._maildir.get_message_metadata(key)
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
