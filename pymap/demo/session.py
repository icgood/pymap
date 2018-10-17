from copy import copy
from datetime import datetime
from typing import Optional, Tuple, List, AbstractSet, Dict, FrozenSet, \
    Iterable, Collection

from pysasl import AuthenticationCredentials

from pymap.exceptions import MailboxNotFound, MailboxConflict
from pymap.flags import FlagOp
from pymap.interfaces.session import SessionInterface
from pymap.parsing.specials import SequenceSet, SearchKey, FetchAttribute, Flag
from pymap.parsing.specials.flag import Deleted
from pymap.search import SearchParams, SearchCriteriaSet
from pymap.selected import SelectedMailbox
from .mailbox import Mailbox
from .message import Message
from .state import State

__all__ = ['Session']


class Session(SessionInterface):

    def __init__(self, user: str) -> None:
        super().__init__()
        self.user = user
        self.mailboxes: Dict[str, Mailbox] = {}

    @classmethod
    def _sessions(cls, name) -> Collection[SelectedMailbox]:
        return State.mailboxes[name].sessions

    @classmethod
    def _get_updates(cls, selected: Optional[SelectedMailbox]) \
            -> Optional[SelectedMailbox]:
        if selected is not None and selected.name in State.mailboxes:
            return copy(selected)
        else:
            return None

    def _check_selected(self, selected: SelectedMailbox) \
            -> Tuple[Mailbox, SelectedMailbox]:
        name = selected.name
        if name not in State.mailboxes:
            raise MailboxNotFound(name)
        return self.mailboxes[name], selected

    def _get_mailbox(self, name: str, selected: Optional[SelectedMailbox]) \
            -> Tuple[Mailbox, Optional[SelectedMailbox]]:
        if name not in State.mailboxes:
            raise MailboxNotFound(name)
        elif name in self.mailboxes:
            return self.mailboxes[name], self._get_updates(selected)
        else:
            mbx, _ = Mailbox.load(name, self, True)
            return mbx, self._get_updates(selected)

    @classmethod
    def _iter_messages(cls, mbx: Mailbox, sequences: SequenceSet) \
            -> Iterable[Tuple[int, Message]]:
        if not mbx.messages:
            return
        elif sequences.uid:
            for msg_uid in sequences.iter(mbx.highest_uid):
                msg_idx = mbx.uid_to_idx.get(msg_uid)
                if msg_idx is not None:
                    msg = mbx.messages[msg_idx]
                    yield (msg_idx + 1, msg)
        else:
            for msg_seq in sequences.iter(mbx.exists):
                msg = mbx.messages[msg_seq - 1]
                yield (msg_seq, msg)

    @classmethod
    async def login(cls, credentials: AuthenticationCredentials) \
            -> Optional['Session']:
        if credentials.authcid == 'demouser' \
                and credentials.check_secret('demopass'):
            return cls(credentials.authcid)
        return None

    async def list_mailboxes(self, ref_name: str,
                             filter_: str,
                             subscribed: bool = False,
                             selected: Optional[SelectedMailbox] = None) \
            -> Tuple[List[Tuple[str, bytes, Dict[str, bool]]],
                     Optional[SelectedMailbox]]:
        if subscribed:
            names: Iterable[str] = {
                name for name, mbx in State.mailboxes.items()
                if mbx.subscribed} | {'INBOX'}
        else:
            names = State.mailboxes.keys()
        return [(name, Mailbox.SEP, {}) for name in sorted(names)], \
            self._get_updates(selected)

    async def get_mailbox(self, name: str,
                          selected: Optional[SelectedMailbox] = None) \
            -> Tuple[Mailbox, Optional[SelectedMailbox]]:
        return Mailbox.get_snapshot(name), self._get_updates(selected)

    async def create_mailbox(self, name: str,
                             selected: Optional[SelectedMailbox] = None) \
            -> Optional[SelectedMailbox]:
        if name in State.mailboxes:
            raise MailboxConflict(name)
        _ = State.mailboxes[name]  # noqa
        return self._get_updates(selected)

    async def delete_mailbox(self, name: str,
                             selected: Optional[SelectedMailbox] = None) \
            -> Optional[SelectedMailbox]:
        if name not in State.mailboxes:
            raise MailboxNotFound(name)
        del State.mailboxes[name]
        if name in self.mailboxes:
            del self.mailboxes[name]
        return self._get_updates(selected)

    async def rename_mailbox(self, before_name: str, after_name: str,
                             selected: Optional[SelectedMailbox] = None) \
            -> Optional[SelectedMailbox]:
        if after_name in State.mailboxes:
            raise MailboxConflict(after_name)
        elif before_name not in State.mailboxes:
            raise MailboxNotFound(before_name)
        State.mailboxes[after_name] = State.mailboxes[before_name]
        del State.mailboxes[before_name]
        return self._get_updates(selected)

    async def subscribe(self, name: str,
                        selected: Optional[SelectedMailbox] = None) \
            -> Optional[SelectedMailbox]:
        if name not in State.mailboxes:
            raise MailboxNotFound(name)
        State.mailboxes[name].subscribed = True
        return self._get_updates(selected)

    async def unsubscribe(self, name: str,
                          selected: Optional[SelectedMailbox] = None) \
            -> Optional[SelectedMailbox]:
        if name not in State.mailboxes:
            raise MailboxNotFound(name)
        State.mailboxes[name].subscribed = False
        return self._get_updates(selected)

    @classmethod
    def _increment_next_uid(cls, name) -> int:
        next_uid = State.mailboxes[name].next_uid
        State.mailboxes[name].next_uid += 1
        return next_uid

    async def append_message(self, name: str,
                             message: bytes,
                             flag_set: AbstractSet[Flag],
                             when: Optional[datetime] = None,
                             selected: Optional[SelectedMailbox] = None) \
            -> Optional[SelectedMailbox]:
        mbx, selected = self._get_mailbox(name, selected)
        messages = State.mailboxes[name].messages
        msg_uid = self._increment_next_uid(name)
        msg = Message.parse(msg_uid, message, flag_set & mbx.permanent_flags,
                            internal_date=when)
        messages.append(msg)
        msg_seq = len(messages)
        sessions = self._sessions(name)
        if sessions:
            for session in sessions:
                session.add_message(msg_seq, msg_uid, flag_set)
        else:
            State.mailboxes[name].recent.add(msg_uid)
        return self._get_updates(selected)

    async def select_mailbox(self, name: str, readonly: bool = False) \
            -> Tuple[Mailbox, SelectedMailbox]:
        if name not in State.mailboxes:
            raise MailboxNotFound(name)
        mbx, updates = Mailbox.load(name, self, readonly)
        self.mailboxes[name] = mbx
        return mbx, updates

    async def check_mailbox(self, selected: SelectedMailbox,
                            housekeeping: bool = False) -> SelectedMailbox:
        _, selected = self._check_selected(selected)
        return selected

    async def fetch_messages(self, selected: SelectedMailbox,
                             sequences: SequenceSet,
                             attributes: AbstractSet[FetchAttribute]) \
            -> Tuple[List[Tuple[int, Message]], SelectedMailbox]:
        mbx, selected = self._check_selected(selected)
        messages = list(self._iter_messages(mbx, sequences))
        return messages, selected

    async def search_mailbox(self, selected: SelectedMailbox,
                             keys: FrozenSet[SearchKey]) \
            -> Tuple[Iterable[Tuple[int, Message]], SelectedMailbox]:
        mbx, selected = self._check_selected(selected)
        matching: List[Tuple[int, Message]] = []
        params = SearchParams(selected, max_seq=mbx.highest_seq,
                              max_uid=mbx.highest_uid)
        search = SearchCriteriaSet(keys, params)
        for msg_idx, msg in enumerate(mbx.messages):
            msg_seq = msg_idx + 1
            if search.matches(msg_seq, msg):
                matching.append((msg_seq, msg))
        return matching, selected

    async def expunge_mailbox(self, selected: SelectedMailbox) \
            -> SelectedMailbox:
        mbx, selected = self._check_selected(selected)
        expunged = {}
        for msg_idx in reversed(range(0, mbx.exists)):
            msg = mbx.messages[msg_idx]
            if Deleted in msg.get_flags(selected):
                expunged[msg_idx + 1] = msg.uid
                State.mailboxes[mbx.name].messages[msg_idx:msg_idx + 1] = []
        mbx.reset_messages()
        sorted_expunged = sorted(expunged.items(), key=lambda t: t[0])
        for session in self._sessions(selected.name):
            for msg_seq, msg_uid in sorted_expunged:
                session.remove_message(msg_seq, msg_uid)
        return selected

    async def copy_messages(self, selected: SelectedMailbox,
                            sequences: SequenceSet,
                            mailbox: str) -> SelectedMailbox:
        mbx, selected = self._check_selected(selected)
        dest, _ = self._get_mailbox(mailbox, selected)
        dest_messages = State.mailboxes[mailbox].messages
        results = []
        for msg_seq, msg in self._iter_messages(mbx, sequences):
            dest_uid = self._increment_next_uid(mailbox)
            dest_msg = Message(dest_uid, msg.contents,
                               internal_date=msg.internal_date)
            dest_flags = msg.get_flags(selected)
            dest.update_flags(selected, dest_msg, dest_flags, FlagOp.REPLACE)
            State.mailboxes[mailbox].recent.add(dest_uid)
            dest_messages.append(dest_msg)
            dest_seq = len(dest_messages)
            results.append((dest_seq, dest_flags))
        for session in self._sessions(selected.name):
            for msg_seq, msg_flags in results:
                session.add_fetch(msg_seq, msg_flags)
        return selected

    async def update_flags(self, selected: SelectedMailbox,
                           sequences: SequenceSet,
                           flag_set: AbstractSet[Flag],
                           mode: FlagOp = FlagOp.REPLACE) \
            -> Tuple[List[Tuple[int, Message]], SelectedMailbox]:
        mbx, selected = self._check_selected(selected)
        results = []
        for msg_seq, msg in self._iter_messages(mbx, sequences):
            mbx.update_flags(selected, msg, flag_set, mode)
            new_flags = msg.get_flags(selected)
            for session in self._sessions(selected.name):
                if session != selected:
                    session.add_fetch(msg_seq, new_flags)
            results.append((msg_seq, msg))
        return results, selected
