
import dbm  # type: ignore
import errno
import os
import os.path
import random
import time
from concurrent.futures import TimeoutError
from contextlib import contextmanager
from datetime import datetime
from mailbox import Maildir, MaildirMessage, NoSuchMailboxError  # type: ignore
from typing import Tuple, Sequence, Dict, Optional, AsyncIterable, Iterator, \
    FrozenSet
from weakref import WeakSet

from pymap.concurrent import Event, ReadWriteLock
from pymap.exceptions import MailboxNotFound, MailboxConflict
from pymap.parsing.specials.flag import Flag, Recent
from pymap.selected import SelectedMailbox

from .flags import get_permanent_flags, flags_from_imap, flags_from_maildir
from ..mailbox import MailboxSnapshot, KeyValMessage, KeyValMailbox

__all__ = ['Message', 'MailboxSnapshot', 'Mailbox']

_Db = Dict[str, bytes]


class Message(KeyValMessage):

    @property
    def maildir_msg(self) -> MaildirMessage:
        is_recent = Recent in self.permanent_flags
        flag_str = flags_from_imap(self.permanent_flags - {Recent})
        msg_bytes = self.get_body(binary=True)
        maildir_msg = MaildirMessage(msg_bytes)
        maildir_msg.set_flags(flag_str)
        maildir_msg.set_subdir('new' if is_recent else 'cur')
        if self.internal_date is not None:
            maildir_msg.set_date(self.internal_date.timestamp())
        return maildir_msg

    @classmethod
    def from_maildir(self, uid: int, maildir_msg: MaildirMessage) -> 'Message':
        flag_set = flags_from_maildir(maildir_msg.get_flags())
        if maildir_msg.get_subdir() == 'new':
            flag_set = flag_set | {Recent}
        msg_date = datetime.fromtimestamp(maildir_msg.get_date())
        msg_bytes = bytes(maildir_msg)
        return self.parse(uid, msg_bytes, flag_set, msg_date)


class Mailbox(KeyValMailbox[Message]):

    db_retry_count = 100
    db_retry_delay = 0.1

    def __init__(self, name: str, maildir: Maildir) -> None:
        self._name = name
        self._maildir = maildir
        self._path = maildir._path
        self._uid_validity = 0
        self._messages_lock = ReadWriteLock.for_threading()
        self._folder_cache: Dict[str, 'Mailbox'] = {}
        self._last_selected: WeakSet[SelectedMailbox] = WeakSet()
        self._updated = Event.for_threading()

    @property
    def _db_path(self) -> str:
        return os.path.join(self._path, '.uid')

    @property
    def _tmp_db_path(self) -> str:
        return os.path.join(self._path, 'tmp.uid')

    @contextmanager
    def _dbm_open(self, mode: str, tmp: bool = False) -> Iterator[_Db]:
        path = self._tmp_db_path if tmp else self._db_path
        count = 0
        while True:
            try:
                db = dbm.open(path, mode)
            except dbm.error as exc:
                exc_errno = getattr(exc, 'errno', None)
                if exc_errno != errno.EAGAIN:
                    raise
                count += 1
                if count >= self.db_retry_count:
                    raise TimeoutError()
                time.sleep(self.db_retry_delay)
            else:
                try:
                    yield db
                finally:
                    db.close()
                break

    @property
    def name(self) -> str:
        return self._name

    @property
    def uid_validity(self) -> int:
        return self._uid_validity

    @property
    def permanent_flags(self) -> FrozenSet[Flag]:
        return get_permanent_flags()

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

    def _is_subscribed(self, name: str) -> bool:
        with self._dbm_open('c') as db:
            is_subscribed = db.get('subscribed-' + name)
            return is_subscribed == b'true'

    async def set_subscribed(self, name: str, subscribed: bool) -> None:
        with self._dbm_open('c') as db:
            db['subscribed-' + name] = b'true' if subscribed else b''

    async def list_subscribed(self) -> Sequence[str]:
        return [name for name in self._maildir.list_folders()
                if self._is_subscribed(name)]

    async def list_mailboxes(self) -> Sequence[str]:
        return self._maildir.list_folders()

    async def get_mailbox(self, name: str) -> 'Mailbox':
        if name.upper() == 'INBOX':
            return await self.reset()
        try:
            maildir = self._maildir.get_folder(name)
        except NoSuchMailboxError:
            raise MailboxNotFound(name)
        else:
            if name in self._folder_cache:
                mbx = self._folder_cache[name]
            else:
                mbx = Mailbox(name, maildir)
                self._folder_cache[name] = mbx
            return await mbx.reset()

    async def add_mailbox(self, name: str) -> 'Mailbox':
        if name in self._maildir.list_folders():
            raise MailboxConflict(name)
        maildir = self._maildir.add_folder(name)
        mbx = Mailbox(name, maildir)
        self._folder_cache[name] = mbx
        return await mbx.reset()

    async def remove_mailbox(self, name: str) -> None:
        if name not in self._maildir.list_folders():
            raise MailboxNotFound(name)
        try:
            os.unlink(self._db_path)
            os.unlink(self._tmp_db_path)
        except OSError:
            pass
        self._maildir.get_folder(name).clear()
        self._maildir.remove_folder(name)

    async def rename_mailbox(self, before: str, after: str) -> 'Mailbox':
        mailboxes = self._maildir.list_folders()
        if before not in mailboxes:
            raise MailboxNotFound(before)
        elif after in mailboxes:
            raise MailboxConflict(after)
        raise RuntimeError()  # TODO

    async def get_max_uid(self) -> int:
        with self._dbm_open('r') as db:
            return int(db['max-uid'].decode('ascii'))

    async def add(self, message: Message) -> 'Message':
        async with self.messages_lock.write_lock():
            key = self._maildir.add(message.maildir_msg)
        with self._dbm_open('w') as db:
            new_uid = int(db['max-uid'].decode('ascii')) + 1
            db['max-uid'] = b'%i' % new_uid
            db['uid-%i' % new_uid] = key
            db['key-' + key] = b'%i' % new_uid
        return message.copy(new_uid)

    async def get(self, uid: int) -> Message:
        with self._dbm_open('r') as db:
            key = db['uid-%i' % uid].decode('ascii')
        async with self.messages_lock.read_lock():
            maildir_msg = self._maildir[key]
            return Message.from_maildir(uid, maildir_msg)

    async def delete(self, uid: int) -> None:
        with self._dbm_open('r') as db:
            key = db['uid-%i' % uid].decode('ascii')
        async with self.messages_lock.write_lock():
            del self._maildir[key]

    async def save_flags(self, *messages: Message) -> None:
        keys: Dict[int, str] = {}
        with self._dbm_open('r') as db:
            for message in messages:
                uid = message.uid
                keys[uid] = db['uid-%i' % uid].decode('ascii')
        async with self.messages_lock.write_lock():
            for message in messages:
                key = keys[message.uid]
                is_recent = Recent in message.permanent_flags
                flag_set = message.permanent_flags - {Recent}
                flag_str = flags_from_imap(flag_set)
                maildir_msg = self._maildir[key]
                maildir_msg.set_flags(flag_str)
                maildir_msg.set_subdir('new' if is_recent else 'cur')
                self._maildir[key] = maildir_msg

    async def get_count(self) -> int:
        async with self.messages_lock.read_lock():
            return len(self._maildir)

    async def cleanup(self) -> None:
        self._maildir.clean()
        folders = self._maildir.list_folders()
        async with self.messages_lock.read_lock():
            keys = list(self._maildir.keys())
        with self._dbm_open('w') as db:
            with self._dbm_open('n', tmp=True) as tmp_db:
                tmp_db['uid-validity'] = db['uid-validity']
                tmp_db['max-uid'] = db['max-uid']
                for key in keys:
                    uid = int(db['key-' + key].decode('ascii'))
                    tmp_db['key-' + key] = b'%i' % uid
                    tmp_db['uid-%i' % uid] = key
                for folder in folders:
                    subscribed = db.get('subscribed-' + folder)
                    if subscribed:
                        tmp_db['subscribed-' + folder] = subscribed
            os.replace(self._tmp_db_path, self._db_path)

    async def uids(self) -> AsyncIterable[int]:
        async with self.messages_lock.read_lock():
            keys = sorted(self._maildir.keys())
        with self._dbm_open('r') as db:
            for key in keys:
                yield int(db['key-' + key].decode('ascii'))

    async def messages(self) -> AsyncIterable[Message]:
        async with self.messages_lock.read_lock():
            keys = sorted(self._maildir.keys())
        with self._dbm_open('r') as db:
            for key in keys:
                uid = int(db['key-' + key].decode('ascii'))
                maildir_msg = self._maildir[key]
                yield Message.from_maildir(uid, maildir_msg)

    async def items(self) -> AsyncIterable[Tuple[int, Message]]:
        async with self.messages_lock.read_lock():
            keys = sorted(self._maildir.keys())
        with self._dbm_open('r') as db:
            for key in keys:
                uid = int(db['key-' + key].decode('ascii'))
                maildir_msg = self._maildir[key]
                yield uid, Message.from_maildir(uid, maildir_msg)

    async def reset(self) -> 'Mailbox':
        if os.path.exists(self._db_path):
            with self._dbm_open('r') as db:
                uid_validity = db.get('uid-validity')
                if uid_validity:
                    self._uid_validity = int(uid_validity.decode('ascii'))
                    return self
        async with self.messages_lock.read_lock():
            keys = sorted(self._maildir.keys())
        with self._dbm_open('c') as db:
            self._uid_validity = random.randint(0, 2147483647)
            db['uid-validity'] = b'%i' % self._uid_validity
            max_uid = 0
            for key in keys:
                key_str = 'key-' + key
                if key_str not in db:
                    max_uid += 1
                    uid_str = 'uid-%i' % max_uid
                    db[key_str] = b'%i' % max_uid
                    db[uid_str] = key
            db['max-uid'] = b'%i' % max_uid
        return self
