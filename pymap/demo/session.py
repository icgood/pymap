# Copyright (c) 2015 Ian C. Good
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#

from collections import defaultdict
from copy import copy
from datetime import datetime
from typing import Optional, Tuple, List, AbstractSet, Dict

from pymap.exceptions import MailboxNotFound, MailboxConflict
from pymap.flag import FlagOp, Recent, Deleted
from pymap.interfaces import SessionInterface, MailboxState
from pymap.parsing.specials import SequenceSet, SearchKey, FetchAttribute, Flag
from pymap.structure import MessageStructure
from .mailbox import Mailbox
from .message import Message
from .state import State

__all__ = ['Session']


class Session(SessionInterface):

    def __init__(self, user: str):
        super().__init__()
        self.user = user  # type: str
        self.updates = defaultdict(lambda: {})
        State.sessions.add(self)

    @classmethod
    def _check_selected(cls, selected: Mailbox):
        if selected.name not in State.mailboxes:
            raise MailboxNotFound(selected.name)
        return selected

    @classmethod
    def _get_updates(cls, selected: Optional[Mailbox]) \
            -> Optional[MailboxState]:
        if selected is not None and selected.name in State.mailboxes:
            return copy(selected)
        else:
            return None

    @classmethod
    def _del_mailbox(cls, name):
        for session in State.sessions:
            try:
                del session.mailboxes[name]
            except KeyError:
                pass
        del State.mailboxes[name]

    @classmethod
    async def login(cls, result):
        if result.authcid == 'demouser' and result.check_secret('demopass'):
            return cls(result.authcid)

    async def list_mailboxes(self, ref_name: str,
                             filter_: str,
                             subscribed: bool = False,
                             selected: Optional[Mailbox] = None) \
            -> Tuple[List[Tuple[str, bytes, Dict[str, bool]]],
                     Optional[MailboxState]]:
        return [(name, Mailbox.sep, {}) for name in State.mailboxes.keys()], \
               self._get_updates(selected)

    async def get_mailbox(self, name: str,
                          selected: Optional[Mailbox] = None) \
            -> Tuple[MailboxState, Optional[MailboxState]]:
        if name in State.mailboxes:
            return Mailbox.load(name, self), self._get_updates(selected)
        raise MailboxNotFound(name)

    async def create_mailbox(self, name: str,
                             selected: Optional[Mailbox] = None) \
            -> Optional[MailboxState]:
        if name in State.mailboxes:
            raise MailboxConflict(name)
        _ = State.mailboxes[name]
        return self._get_updates(selected)

    async def delete_mailbox(self, name: str,
                             selected: Optional[Mailbox] = None) \
            -> Optional[MailboxState]:
        if name not in State.mailboxes:
            raise MailboxNotFound(name)
        self._del_mailbox(name)
        return self._get_updates(selected)

    async def rename_mailbox(self, before_name: str, after_name: str,
                             selected: Optional[Mailbox] = None) \
            -> Optional[MailboxState]:
        if after_name in State.mailboxes:
            raise MailboxConflict(after_name)
        elif before_name not in State.mailboxes:
            raise MailboxNotFound(before_name)
        State.mailboxes[after_name] = State.mailboxes[before_name]
        self._del_mailbox(before_name)
        return self._get_updates(selected)

    async def subscribe(self, name: str,
                        selected: Optional[Mailbox] = None) \
            -> Optional[MailboxState]:
        return self._get_updates(selected)

    async def unsubscribe(self, name: str,
                          selected: Optional[Mailbox] = None) \
            -> Optional[MailboxState]:
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
                             selected: Optional[Mailbox] = None) \
            -> Optional[MailboxState]:
        if name not in State.mailboxes:
            raise MailboxNotFound(name)
        mbx = Mailbox.load(name, self)
        msg_uid = self._increment_next_uid(name)
        msg = Message.parse(msg_uid, message, flag_set & mbx.permanent_flags,
                            internal_date=when)
        msg.session_flags.update(self, flag_set & mbx.session_flags | {Recent})
        State.mailboxes[name].messages.append(msg)
        msg_seq = len(State.mailboxes[name].messages)
        for session in State.sessions:
            session.mailboxes[name].updates.add_fetch(
                msg_seq, msg_uid, flag_set)
        return self._get_updates(selected)

    async def check_mailbox(self, selected: Mailbox,
                            housekeeping: bool = False) \
            -> Optional[MailboxState]:
        return self._get_updates(selected)

    async def fetch_messages(self, selected: Mailbox,
                             sequences: SequenceSet,
                             attributes: AbstractSet[FetchAttribute]) \
            -> Tuple[List[Tuple[int, MessageStructure]],
                     Optional[MailboxState]]:
        mbx = self._check_selected(selected)
        messages = []
        for msg_seq in sequences.iter(mbx.exists):
            msg = mbx.messages[msg_seq - 1]
            messages.append((msg_seq, msg))
        return messages, self._get_updates(selected)

    async def search_mailbox(self, selected: Mailbox,
                             keys: List[SearchKey]) \
            -> Tuple[List[int], Optional[MailboxState]]:
        raise NotImplementedError

    async def expunge_mailbox(self, selected: Mailbox) \
            -> Optional[MailboxState]:
        mbx = self._check_selected(selected)
        expunged = set()
        for i, msg in enumerate(mbx.messages):
            if Deleted in msg.get_flags(selected):
                expunged.add(i + 1)
                State.mailboxes[mbx.name].messages[i:i + 1] = []
        for session in State.sessions:
            session.mailboxes[mbx.name].updates.add_expunge(*expunged)
            session.mailboxes[mbx.name].reset_messages()
        return self._get_updates(selected)

    async def copy_messages(self, selected: Mailbox,
                            sequences: SequenceSet,
                            mailbox: str) \
            -> Optional[MailboxState]:
        raise NotImplementedError

    async def update_flags(self, selected: Mailbox,
                           sequences: SequenceSet,
                           flag_set: AbstractSet[bytes],
                           mode: FlagOp = FlagOp.REPLACE,
                           silent: bool = False) \
            -> Optional[MailboxState]:
        mbx = self._check_selected(selected)
        for msg_seq in sequences.iter(mbx.exists):
            msg = mbx.messages[msg_seq - 1]
            before_flags = frozenset(msg.permanent_flags)
            if mode == FlagOp.ADD:
                msg.permanent_flags |= flag_set
            elif mode == FlagOp.DELETE:
                msg.permanent_flags -= flag_set
            else:
                msg.permanent_flags = flag_set
            if before_flags != msg.permanent_flags and not silent:
                for session in State.sessions:
                    Mailbox(mbx.name, session).add_fetch(msg_seq, msg)
        return self._get_updates(selected)
