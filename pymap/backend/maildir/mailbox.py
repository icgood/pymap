
import errno
import os
import os.path
from datetime import datetime
from mailbox import Maildir as _Maildir, MaildirMessage  # type: ignore
from typing import Dict, Optional, FrozenSet, Iterable, AsyncIterable
from typing_extensions import Final

from pymap.concurrent import ReadWriteLock
from pymap.context import subsystem
from pymap.exceptions import MailboxNotFound, MailboxConflict, \
    MailboxHasChildren, NotSupportedError
from pymap.flags import FlagOp
from pymap.interfaces.message import CachedMessage
from pymap.listtree import ListTree
from pymap.mailbox import MailboxSnapshot
from pymap.message import BaseMessage, BaseLoadedMessage
from pymap.mime import MessageContent
from pymap.parsing.message import PreparedMessage
from pymap.parsing.specials import ObjectId, FetchRequirement
from pymap.parsing.specials.flag import Flag, Seen
from pymap.selected import SelectedSet, SelectedMailbox

from .flags import MaildirFlags
from .io import NoChanges
from .layout import MaildirLayout
from .subscriptions import Subscriptions
from .uidlist import Record, UidList
from ..mailbox import SavedMessage, MailboxDataInterface, MailboxSetInterface

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


class Message(BaseMessage):

    __slots__ = ['recent', '_maildir', '_key']

    def __init__(self, uid: int, internal_date: datetime,
                 permanent_flags: Iterable[Flag], *, expunged: bool = False,
                 email_id: ObjectId = None, thread_id: ObjectId = None,
                 recent: bool = False, maildir: Maildir = None,
                 key: str = None) -> None:
        super().__init__(uid, internal_date, permanent_flags,
                         expunged=expunged, email_id=email_id,
                         thread_id=thread_id)
        self.recent: Final = recent
        self._maildir = maildir
        self._key = key

    async def load_content(self, requirement: FetchRequirement) \
            -> 'LoadedMessage':
        if self._key is None or self._maildir is None \
                or not requirement.overlaps(FetchRequirement.CONTENT):
            return LoadedMessage(self, requirement, None)
        try:
            maildir_msg = self._maildir.get_message(self._key)
        except (KeyError, FileNotFoundError):
            return LoadedMessage(self, requirement, None)
        else:
            content = MessageContent.parse(bytes(maildir_msg))
            return LoadedMessage(self, requirement, content)

    @classmethod
    def to_maildir(cls, prepared_msg: PreparedMessage, recent: bool,
                   maildir_flags: MaildirFlags) -> MaildirMessage:
        flag_str = maildir_flags.to_maildir(prepared_msg.flag_set)
        when = prepared_msg.when or datetime.now()
        literal: bytes = prepared_msg.ref
        maildir_msg = MaildirMessage(literal)
        maildir_msg.set_flags(flag_str)
        maildir_msg.set_subdir('new' if recent else 'cur')
        maildir_msg.set_date(when.timestamp())
        return maildir_msg

    @classmethod
    def from_maildir(cls, uid: int, maildir_msg: MaildirMessage,
                     maildir: Maildir, key: str,
                     email_id: Optional[ObjectId],
                     thread_id: Optional[ObjectId],
                     maildir_flags: 'MaildirFlags') -> 'Message':
        flag_set = maildir_flags.from_maildir(maildir_msg.get_flags())
        recent = maildir_msg.get_subdir() == 'new'
        msg_dt = datetime.fromtimestamp(maildir_msg.get_date())
        return cls(uid, msg_dt, flag_set,
                   email_id=email_id, thread_id=thread_id,
                   recent=recent, maildir=maildir, key=key)


class LoadedMessage(BaseLoadedMessage):
    pass


class MailboxData(MailboxDataInterface[Message]):

    db_retry_count = 100
    db_retry_delay = 0.1
    filename_db = '.uid'
    filename_tmp_db = 'tmp.uid'

    def __init__(self, mailbox_id: ObjectId, maildir: Maildir,
                 path: str) -> None:
        super().__init__()
        self._mailbox_id = mailbox_id
        self._maildir = maildir
        self._path = path
        self._uid_validity = 0
        self._next_uid = 0
        self._flags: Optional[MaildirFlags] = None
        self._messages_lock = subsystem.get().new_rwlock()
        self._selected_set = SelectedSet()

    @classmethod
    def _get_object_id(cls, rec: Record, field: str) -> Optional[ObjectId]:
        return ObjectId.maybe(rec.fields.get(field))

    @property
    def mailbox_id(self) -> ObjectId:
        return self._mailbox_id

    @property
    def readonly(self) -> bool:
        return False

    @property
    def uid_validity(self) -> int:
        return self._uid_validity

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

    async def update_selected(self, selected: SelectedMailbox) \
            -> SelectedMailbox:
        all_messages = [msg async for msg in self.messages()]
        selected.set_messages(all_messages)
        return selected

    async def save(self, message: bytes) -> SavedMessage:
        email_id = ObjectId.random_email_id()
        thread_id = ObjectId.random_thread_id()
        return SavedMessage(email_id, thread_id, message)

    async def add(self, message: PreparedMessage, *,
                  recent: bool = False) -> Message:
        maildir = self._maildir
        async with self.messages_lock.write_lock():
            maildir_msg = Message.to_maildir(message, recent,
                                             self.maildir_flags)
            key = maildir.add(maildir_msg)
            filename = key + ':' + maildir_msg.get_info()
        email_id = message.email_id
        thread_id = message.thread_id
        async with UidList.with_write(self._path) as uidl:
            fields = {'E': str(email_id), 'T': str(thread_id)}
            new_rec = Record(uidl.next_uid, fields, filename)
            uidl.next_uid += 1
            uidl.set(new_rec)
        return Message.from_maildir(
            new_rec.uid, maildir_msg, maildir, key, email_id, thread_id,
            self.maildir_flags)

    async def get(self, uid: int, cached_msg: CachedMessage = None) \
            -> Optional[Message]:
        async with UidList.with_read(self._path) as uidl:
            next_uid = uidl.next_uid
            if uid < 1 or uid >= next_uid:
                raise IndexError(uid)
            try:
                record = uidl.get(uid)
            except KeyError:
                if cached_msg is not None:
                    return Message(cached_msg.uid, cached_msg.internal_date,
                                   cached_msg.permanent_flags, expunged=True,
                                   email_id=cached_msg.email_id,
                                   thread_id=cached_msg.thread_id)
                else:
                    return None
        maildir = self._maildir
        key = record.key
        email_id = self._get_object_id(record, 'E')
        thread_id = self._get_object_id(record, 'T')
        async with self.messages_lock.read_lock():
            try:
                maildir_msg = maildir.get_message_metadata(key)
            except (KeyError, FileNotFoundError):
                if cached_msg is not None:
                    return Message(cached_msg.uid, cached_msg.internal_date,
                                   cached_msg.permanent_flags, expunged=True,
                                   email_id=cached_msg.email_id,
                                   thread_id=cached_msg.thread_id)
                else:
                    return None
            return Message.from_maildir(
                uid, maildir_msg, maildir, key, email_id, thread_id,
                self.maildir_flags)

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

    async def update_flags(self, messages: Iterable[Message],
                           flag_set: FrozenSet[Flag], mode: FlagOp) -> None:
        msgs_map = {msg.uid: msg for msg in messages}
        async with UidList.with_read(self._path) as uidl:
            records = uidl.get_all(msgs_map.keys())
        async with self.messages_lock.write_lock():
            for uid, rec in records.items():
                key = rec.key
                msg = msgs_map[uid]
                msg.permanent_flags = mode.apply(msg.permanent_flags, flag_set)
                flag_str = self.maildir_flags.to_maildir(msg.permanent_flags)
                try:
                    maildir_msg = self._maildir.get_message_metadata(key)
                except (KeyError, FileNotFoundError):
                    continue
                maildir_msg.set_flags(flag_str)
                maildir_msg.set_subdir('new' if msg.recent else 'cur')
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

    async def messages(self) -> AsyncIterable[Message]:
        async with UidList.with_read(self._path) as uidl:
            uids = {rec.uid: rec for rec in uidl.records}
        maildir = self._maildir
        async with self.messages_lock.read_lock():
            for uid, rec in uids.items():
                email_id = self._get_object_id(rec, 'E')
                thread_id = self._get_object_id(rec, 'T')
                try:
                    maildir_msg = maildir.get_message_metadata(rec.key)
                except (KeyError, FileNotFoundError):
                    pass
                else:
                    yield Message.from_maildir(
                        uid, maildir_msg, maildir, rec.key,
                        email_id, thread_id, self.maildir_flags)

    async def reset(self) -> 'MailboxData':
        keys = await self._get_keys()
        async with UidList.with_write(self._path) as uidl:
            for rec in uidl.records:
                keys.pop(rec.key, None)
            if not keys:
                raise NoChanges()
            for key, info in keys.items():
                filename = key + ':' + info
                fields = {'E': str(ObjectId.random_email_id()),
                          'T': str(ObjectId.random_thread_id())}
                new_rec = Record(uidl.next_uid, fields, filename)
                uidl.next_uid += 1
                uidl.set(new_rec)
        self._uid_validity = uidl.uid_validity
        self._next_uid = uidl.next_uid
        return self

    async def snapshot(self) -> MailboxSnapshot:
        exists = 0
        recent = 0
        unseen = 0
        first_unseen: Optional[int] = None
        next_uid = self._next_uid
        async for msg in self.messages():
            exists += 1
            if msg.recent:
                recent += 1
            if Seen not in msg.permanent_flags:
                unseen += 1
                if first_unseen is None:
                    first_unseen = exists
        return MailboxSnapshot(self.mailbox_id, self.readonly,
                               self.uid_validity, self.permanent_flags,
                               self.session_flags, exists, recent, unseen,
                               first_unseen, next_uid)

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
        self._inbox_maildir = maildir
        self._path = layout.path
        self._cache: Dict[str, 'MailboxData'] = {}

    @property
    def delimiter(self) -> str:
        return '/'

    async def set_subscribed(self, name: str, subscribed: bool) -> None:
        async with Subscriptions.with_write(self._path) as subs:
            subs.set(name, subscribed)

    async def list_subscribed(self) -> ListTree:
        async with Subscriptions.with_read(self._path) as subs:
            subscribed = frozenset(subs.subscribed)
        mailboxes = [name for name in self._layout.list_folders(self.delimiter)
                     if name in subscribed]
        return ListTree(self.delimiter).update('INBOX', *mailboxes)

    async def list_mailboxes(self) -> ListTree:
        mailboxes = self._layout.list_folders(self.delimiter)
        return ListTree(self.delimiter).update('INBOX', *mailboxes)

    async def get_mailbox(self, name: str,
                          try_create: bool = False) -> 'MailboxData':
        if name == 'INBOX':
            maildir = self._inbox_maildir
        else:
            try:
                maildir = self._layout.get_folder(name, self.delimiter)
            except FileNotFoundError:
                raise MailboxNotFound(name, try_create)
        if name in self._cache:
            mbx = self._cache[name]
        else:
            path = self._layout.get_path(name, self.delimiter)
            async with UidList.with_open(path) as uidl:
                mailbox_id = ObjectId(uidl.global_uid)
            mbx = MailboxData(mailbox_id, maildir, path)
            self._cache[name] = mbx
        return await mbx.reset()

    async def add_mailbox(self, name: str) -> ObjectId:
        try:
            self._layout.add_folder(name, self.delimiter)
        except FileExistsError:
            raise MailboxConflict(name)
        path = self._layout.get_path(name, self.delimiter)
        async with UidList.with_open(path) as uidl:
            return ObjectId(uidl.global_uid)

    async def delete_mailbox(self, name: str) -> None:
        try:
            self._layout.remove_folder(name, self.delimiter)
        except FileNotFoundError:
            raise MailboxNotFound(name)
        except OSError as exc:
            if exc.errno == errno.ENOTEMPTY:
                raise MailboxHasChildren(name) from exc
            raise exc

    async def rename_mailbox(self, before: str, after: str) -> None:
        if before == 'INBOX':
            raise NotSupportedError()  # TODO
        else:
            self._layout.rename_folder(before, after, self.delimiter)
