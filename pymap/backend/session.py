
from abc import abstractmethod
from asyncio import shield
from typing import Tuple, Optional, FrozenSet, Iterable, Sequence, List
from typing_extensions import Protocol

from pymap.concurrent import Event
from pymap.config import IMAPConfig
from pymap.exceptions import MailboxNotFound, MailboxReadOnly
from pymap.flags import FlagOp, SessionFlags, PermanentFlags
from pymap.listtree import ListTree
from pymap.mailbox import MailboxSnapshot
from pymap.message import AppendMessage
from pymap.parsing.specials import SequenceSet, SearchKey, \
    FetchAttribute, FetchRequirement
from pymap.parsing.specials.flag import Flag, Deleted, Seen
from pymap.parsing.response.code import AppendUid, CopyUid
from pymap.interfaces.session import SessionInterface
from pymap.search import SearchParams, SearchCriteriaSet
from pymap.selected import SelectedMailbox

from .mailbox import MailboxDataInterface, MailboxSetInterface, MessageT

__all__ = ['BaseSession']


class BaseSession(SessionInterface, Protocol[MessageT]):
    """Base implementation of
    :class:`~pymap.interfaces.session.SessionInterface` intended for use by
    most backends.

    """

    @property
    @abstractmethod
    def config(self) -> IMAPConfig:
        ...

    @property
    @abstractmethod
    def mailbox_set(self) \
            -> MailboxSetInterface[MailboxDataInterface[MessageT]]:
        ...

    async def _load_updates(self, selected: Optional[SelectedMailbox],
                            mbx: Optional[MailboxDataInterface[MessageT]]) \
            -> Optional[SelectedMailbox]:
        if selected:
            if not mbx or selected.name != mbx.name:
                try:
                    mbx = await self.mailbox_set.get_mailbox(selected.name)
                except MailboxNotFound:
                    selected.set_deleted()
                    return selected
            return await mbx.update_selected(selected)
        return selected

    @classmethod
    def _find_selected(cls, selected: Optional[SelectedMailbox],
                       mbx: MailboxDataInterface[MessageT]) \
            -> Optional[SelectedMailbox]:
        if selected and selected.name == mbx.name:
            return selected
        return mbx.selected_set.any_selected

    async def list_mailboxes(self, ref_name: str, filter_: str,
                             subscribed: bool = False,
                             selected: SelectedMailbox = None) \
            -> Tuple[Iterable[Tuple[str, Optional[str], Sequence[bytes]]],
                     Optional[SelectedMailbox]]:
        delimiter = self.mailbox_set.delimiter
        if filter_:
            list_tree = ListTree(delimiter).update('INBOX')
            if subscribed:
                list_tree.update(*await self.mailbox_set.list_subscribed())
            else:
                list_tree.update(*await self.mailbox_set.list_mailboxes())
            ret = [(entry.name, delimiter, entry.attributes)
                   for entry in list_tree.list_matching(ref_name, filter_)]
        else:
            ret = [("", delimiter, [b'Noselect'])]
        return ret, await self._load_updates(selected, None)

    async def get_mailbox(self, name: str, selected: SelectedMailbox = None) \
            -> Tuple[MailboxSnapshot, Optional[SelectedMailbox]]:
        mbx = await self.mailbox_set.get_mailbox(name)
        snapshot = await mbx.snapshot()
        return snapshot, await self._load_updates(selected, mbx)

    async def create_mailbox(self, name: str,
                             selected: SelectedMailbox = None) \
            -> Optional[SelectedMailbox]:
        await self.mailbox_set.add_mailbox(name)
        return await self._load_updates(selected, None)

    async def delete_mailbox(self, name: str,
                             selected: SelectedMailbox = None) \
            -> Optional[SelectedMailbox]:
        await self.mailbox_set.delete_mailbox(name)
        return await self._load_updates(selected, None)

    async def rename_mailbox(self, before_name: str, after_name: str,
                             selected: SelectedMailbox = None) \
            -> Optional[SelectedMailbox]:
        await self.mailbox_set.rename_mailbox(before_name, after_name)
        return await self._load_updates(selected, None)

    async def subscribe(self, name: str, selected: SelectedMailbox = None) \
            -> Optional[SelectedMailbox]:
        mbx = await self.mailbox_set.get_mailbox('INBOX')
        await self.mailbox_set.set_subscribed(name, True)
        return await self._load_updates(selected, mbx)

    async def unsubscribe(self, name: str, selected: SelectedMailbox = None) \
            -> Optional[SelectedMailbox]:
        mbx = await self.mailbox_set.get_mailbox('INBOX')
        await self.mailbox_set.set_subscribed(name, False)
        return await self._load_updates(selected, mbx)

    async def append_messages(self, name: str,
                              messages: Sequence[AppendMessage],
                              selected: SelectedMailbox = None) \
            -> Tuple[AppendUid, Optional[SelectedMailbox]]:
        mbx = await self.mailbox_set.get_mailbox(name, try_create=True)
        if mbx.readonly:
            raise MailboxReadOnly(name)
        dest_selected = self._find_selected(selected, mbx)
        uids: List[int] = []
        for append_msg in messages:
            msg = mbx.parse_message(append_msg)
            msg = await mbx.add(msg, recent=not dest_selected)
            if dest_selected:
                dest_selected.session_flags.add_recent(msg.uid)
            uids.append(msg.uid)
        mbx.selected_set.updated.set()
        return (AppendUid(mbx.uid_validity, uids),
                await self._load_updates(selected, mbx))

    async def select_mailbox(self, name: str, readonly: bool = False) \
            -> Tuple[MailboxSnapshot, SelectedMailbox]:
        mbx = await self.mailbox_set.get_mailbox(name)
        selected = SelectedMailbox(name, readonly or mbx.readonly,
                                   PermanentFlags(mbx.permanent_flags),
                                   SessionFlags(mbx.session_flags),
                                   selected_set=mbx.selected_set)
        if not selected.readonly:
            await mbx.claim_recent(selected)
        snapshot = await mbx.snapshot()
        return snapshot, await mbx.update_selected(selected)

    async def check_mailbox(self, selected: SelectedMailbox, *,
                            wait_on: Event = None,
                            housekeeping: bool = False) -> SelectedMailbox:
        mbx = await self.mailbox_set.get_mailbox(selected.name)
        if housekeeping:
            await shield(mbx.cleanup())
        if wait_on is not None:
            either_event = wait_on.or_event(mbx.selected_set.updated)
            await either_event.wait()
        return await mbx.update_selected(selected)

    async def fetch_messages(self, selected: SelectedMailbox,
                             sequence_set: SequenceSet,
                             attributes: FrozenSet[FetchAttribute]) \
            -> Tuple[Iterable[Tuple[int, MessageT]], SelectedMailbox]:
        mbx = await self.mailbox_set.get_mailbox(selected.name)
        req = FetchRequirement.reduce({attr.requirement
                                       for attr in attributes})
        ret = [(seq, msg) async for seq, msg
               in mbx.find(sequence_set, selected, req)]
        if not selected.readonly and any(attr.set_seen for attr in attributes):
            seen_set = frozenset([Seen])
            for _, msg in ret:
                msg.update_flags(seen_set, FlagOp.ADD)
            await mbx.save_flags(msg for _, msg in ret)
            mbx.selected_set.updated.set()
        return ret, await mbx.update_selected(selected)

    async def search_mailbox(self, selected: SelectedMailbox,
                             keys: FrozenSet[SearchKey]) \
            -> Tuple[Iterable[Tuple[int, MessageT]], SelectedMailbox]:
        mbx = await self.mailbox_set.get_mailbox(selected.name)
        req = FetchRequirement.reduce({key.requirement for key in keys})
        ret: List[Tuple[int, MessageT]] = []
        params = SearchParams(selected,
                              disabled=self.config.disable_search_keys)
        search = SearchCriteriaSet(keys, params)
        async for seq, msg in mbx.find(search.sequence_set, selected, req):
            if search.matches(seq, msg):
                ret.append((seq, msg))
        return ret, await mbx.update_selected(selected)

    async def expunge_mailbox(self, selected: SelectedMailbox,
                              uid_set: SequenceSet = None) -> SelectedMailbox:
        if selected.readonly:
            raise MailboxReadOnly(selected.name)
        mbx = await self.mailbox_set.get_mailbox(selected.name)
        if not uid_set:
            uid_set = SequenceSet.all(uid=True)
        expunge_uids: List[int] = []
        async for _, msg in mbx.find(uid_set, selected):
            if not msg.expunged and Deleted in msg.get_flags():
                expunge_uids.append(msg.uid)
        await mbx.delete(expunge_uids)
        mbx.selected_set.updated.set()
        return await mbx.update_selected(selected)

    async def copy_messages(self, selected: SelectedMailbox,
                            sequence_set: SequenceSet,
                            mailbox: str) \
            -> Tuple[Optional[CopyUid], SelectedMailbox]:
        mbx = await self.mailbox_set.get_mailbox(selected.name)
        dest = await self.mailbox_set.get_mailbox(mailbox, try_create=True)
        if dest.readonly:
            raise MailboxReadOnly(mailbox)
        req = FetchRequirement.BODY
        dest_selected = self._find_selected(selected, dest)
        uids: List[Tuple[int, int]] = []
        async for _, msg in mbx.find(sequence_set, selected, req):
            if not msg.expunged:
                source_uid = msg.uid
                msg = await dest.add(msg, recent=not dest_selected)
                if dest_selected:
                    dest_selected.session_flags.add_recent(msg.uid)
                uids.append((source_uid, msg.uid))
        dest.selected_set.updated.set()
        return (CopyUid(dest.uid_validity, uids),
                await mbx.update_selected(selected))

    async def update_flags(self, selected: SelectedMailbox,
                           sequence_set: SequenceSet,
                           flag_set: FrozenSet[Flag],
                           mode: FlagOp = FlagOp.REPLACE) \
            -> Tuple[Iterable[Tuple[int, MessageT]], SelectedMailbox]:
        if selected.readonly:
            raise MailboxReadOnly(selected.name)
        mbx = await self.mailbox_set.get_mailbox(selected.name)
        permanent_flags = selected.permanent_flags & flag_set
        messages: List[Tuple[int, MessageT]] = []
        async for msg_seq, msg in mbx.find(sequence_set, selected):
            if not msg.expunged:
                msg.update_flags(permanent_flags, mode)
                selected.session_flags.update(msg.uid, flag_set, mode)
            messages.append((msg_seq, msg))
        await mbx.save_flags(msg for _, msg in messages)
        mbx.selected_set.updated.set()
        return messages, await mbx.update_selected(selected)
