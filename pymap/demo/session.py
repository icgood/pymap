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

from datetime import datetime
from typing import Optional, Tuple, List, Dict, AbstractSet

from pymap.exceptions import MailboxNotFound, MailboxConflict
from pymap.flag import FlagOp
from pymap.interfaces import SessionInterface, MailboxState
from pymap.parsing.specials import SequenceSet, SearchKey, FetchAttribute
from pymap.structure import MessageStructure
from pymap.updates import MailboxUpdates
from .mailbox import Mailbox
from .message import Message
from .state import State

__all__ = ['Session']


class Session(SessionInterface):

    def __init__(self, user: str):
        super().__init__()
        self.mailboxes = (
                {name: Mailbox(name) for name in State.mailboxes.keys()}
        )  # type: Dict[str, Mailbox]
        self.user = user  # type: str
        State.sessions.add(self)

    def _get_selected(self, selected: str) -> Mailbox:
        if selected not in self.mailboxes:
            raise MailboxNotFound(selected)
        return self.mailboxes[selected]

    def _get_updates(self, selected: Optional[str]) \
            -> Optional[MailboxUpdates]:
        if selected is not None and selected in self.mailboxes:
            updates = self.mailboxes[selected].updates
            updates.add_recent(*State.mailboxes[selected].recent)
            State.mailboxes[selected].recent.clear()
            return updates
        else:
            return None

    @classmethod
    async def login(cls, result):
        if result.authcid == 'demouser' and result.check_secret('demopass'):
            return cls(result.authcid)

    async def list_mailboxes(self, ref_name: str,
                             filter_: str,
                             subscribed: bool = False,
                             selected: Optional[str] = None) \
            -> Tuple[List[Tuple[str, bytes, MailboxState]],
                     Optional[MailboxUpdates]]:
        return [(name, mailbox.sep, mailbox)
                for name, mailbox in self.mailboxes.items()], \
               self._get_updates(selected)

    async def get_mailbox(self, name: str, selected: Optional[str] = None) \
            -> Tuple[MailboxState, Optional[MailboxUpdates]]:
        if name in self.mailboxes:
            return self.mailboxes[name], self._get_updates(selected)
        raise MailboxNotFound(name)

    async def create_mailbox(self, name: str, selected: Optional[str] = None) \
            -> Optional[MailboxUpdates]:
        if name in State.mailboxes:
            raise MailboxConflict(name)
        for session in State.sessions:
            session.mailboxes[name] = State.mailboxes[name]
        return self._get_updates(selected)

    async def delete_mailbox(self, name: str, selected: Optional[str] = None) \
            -> Optional[MailboxUpdates]:
        if name not in State.mailboxes:
            raise MailboxNotFound(name)
        for session in State.sessions:
            del session.mailboxes[name]
        del State.mailboxes[name]
        return self._get_updates(selected)

    async def rename_mailbox(self, before_name: str, after_name: str,
                             selected: Optional[str] = None) \
            -> Optional[MailboxUpdates]:
        if after_name in State.mailboxes:
            raise MailboxConflict(after_name)
        elif before_name not in State.mailboxes:
            raise MailboxNotFound(before_name)
        for session in State.sessions:
            session.mailboxes[after_name] = session.mailboxes[before_name]
            del session.mailboxes[before_name]
        State.mailboxes[after_name] = State.mailboxes[before_name]
        del State.mailboxes[before_name]
        return self._get_updates(selected)

    async def subscribe(self, name: str, selected: Optional[str] = None) \
            -> Optional[MailboxUpdates]:
        return self._get_updates(selected)

    async def unsubscribe(self, name: str, selected: Optional[str] = None) \
            -> Optional[MailboxUpdates]:
        return self._get_updates(selected)

    @classmethod
    def _increment_next_uid(cls, name) -> int:
        next_uid = State.mailboxes[name].next_uid
        State.mailboxes[name].next_uid += 1
        return next_uid

    async def append_message(self, name: str,
                             message: bytes,
                             flag_set: AbstractSet[bytes],
                             when: Optional[datetime] = None,
                             selected: Optional[str] = None) \
            -> Optional[MailboxUpdates]:
        if name not in self.mailboxes:
            raise MailboxNotFound(name)
        msg_uid = self._increment_next_uid(name)
        msg = Message(msg_uid, flag_set, message, when=when)
        State.mailboxes[name].messages.append(msg)
        msg_seq = len(State.mailboxes[name].messages)
        for session in State.sessions:
            session.mailboxes[name].updates.add_fetch(
                msg_seq, flag_set, msg_uid)
        updates = self._get_updates(selected)
        updates.add_recent(msg_uid)
        return updates

    async def check_mailbox(self, selected: str, housekeeping: bool = False) \
            -> Optional[MailboxUpdates]:
        return self._get_updates(selected)

    async def fetch_messages(self, selected: str,
                             sequences: SequenceSet,
                             attributes: AbstractSet[FetchAttribute]) \
            -> Tuple[List[Tuple[int, MessageStructure]],
                     Optional[MailboxUpdates]]:
        mbx = self._get_selected(selected)
        updates = self._get_updates(selected)
        return [(i, mbx.messages[i - 1])
                for i in sequences.iter(mbx.exists)], updates

    async def search_mailbox(self, selected: str,
                             keys: List[SearchKey]) \
            -> Tuple[List[int], Optional[MailboxUpdates]]:
        raise NotImplementedError

    async def expunge_mailbox(self, selected: str) \
            -> Optional[MailboxUpdates]:
        mbx = self._get_selected(selected)
        expunged = set()
        for i, msg in enumerate(mbx.messages):
            if br'\Deleted' in msg.flags:
                expunged.add(i + 1)
                State.mailboxes[selected].messages[i:i + 1] = []
        for session in State.sessions:
            session.mailboxes[selected].updates.add_expunge(*expunged)
            session.mailboxes[selected].reset_messages()
        return self._get_updates(selected)

    async def copy_messages(self, selected: str,
                            sequences: SequenceSet,
                            mailbox: str) \
            -> Optional[MailboxUpdates]:
        raise NotImplementedError

    async def update_flags(self, selected: str,
                           sequences: SequenceSet,
                           flag_set: AbstractSet[bytes],
                           mode: FlagOp = FlagOp.REPLACE,
                           silent: bool = False) \
            -> Optional[MailboxUpdates]:
        mbx = self._get_selected(selected)
        for msg_seq, msg in enumerate(mbx.messages):
            before_flags = msg.flags
            if mode == 'add':
                msg.flags = msg.flags | flag_set
            elif mode == 'subtract':
                msg.flags = msg.flags - flag_set
            else:
                msg.flags = flag_set
            if before_flags != msg.flags and not silent:
                for session in State.sessions:
                    updates = session.mailboxes[selected].updates
                    updates.add_fetch(msg_seq, msg.flags, msg.uid)
        return self._get_updates(selected)
