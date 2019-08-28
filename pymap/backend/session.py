
from abc import abstractmethod
from asyncio import shield
from typing import Generic, Tuple, Optional, FrozenSet, Iterable, \
    Sequence, List

from pymap.concurrent import Event
from pymap.config import IMAPConfig
from pymap.exceptions import MailboxNotFound, MailboxReadOnly
from pymap.flags import FlagOp, SessionFlags, PermanentFlags
from pymap.interfaces.filter import FilterSetInterface
from pymap.interfaces.message import AppendMessage
from pymap.interfaces.session import SessionInterface
from pymap.mailbox import MailboxSnapshot
from pymap.parsing.specials import SequenceSet, SearchKey, ObjectId, \
    FetchRequirement
from pymap.parsing.specials.flag import Flag, Seen
from pymap.parsing.response.code import AppendUid, CopyUid
from pymap.search import SearchParams, SearchCriteriaSet
from pymap.selected import SelectedMailbox

from .mailbox import MailboxDataInterface, MailboxSetInterface, MessageT

__all__ = ['BaseSession']


class BaseSession(SessionInterface, Generic[MessageT]):
    """Base implementation of
    :class:`~pymap.interfaces.session.SessionInterface` intended for use by
    most backends.

    Args:
        owner: The logged-in user name.

    """

    def __init__(self, owner: str) -> None:
        super().__init__()
        self._owner = owner

    @property
    def owner(self) -> str:
        return self._owner

    @property
    @abstractmethod
    def config(self) -> IMAPConfig:
        ...

    @property
    @abstractmethod
    def mailbox_set(self) \
            -> MailboxSetInterface[MailboxDataInterface[MessageT]]:
        ...

    @property
    def filter_set(self) -> Optional[FilterSetInterface]:
        return None

    async def cleanup(self) -> None:
        pass

    async def _load_updates(self, selected: Optional[SelectedMailbox],
                            mbx: Optional[MailboxDataInterface[MessageT]]) \
            -> Optional[SelectedMailbox]:
        if selected:
            if not mbx or selected.mailbox_id != mbx.mailbox_id:
                try:
                    mbx = await self._get_selected(selected)
                except MailboxNotFound:
                    selected.set_deleted()
                    return selected
            return await mbx.update_selected(selected)
        return selected

    @classmethod
    def _pick_selected(cls, selected: Optional[SelectedMailbox],
                       mbx: MailboxDataInterface[MessageT]) \
            -> Optional[SelectedMailbox]:
        if selected and selected.mailbox_id == mbx.mailbox_id:
            return selected
        return mbx.selected_set.any_selected

    async def _get_selected(self, selected: SelectedMailbox) \
            -> MailboxDataInterface[MessageT]:
        return await self.mailbox_set.get_mailbox(selected.lookup)

    async def list_mailboxes(self, ref_name: str, filter_: str,
                             subscribed: bool = False,
                             selected: SelectedMailbox = None) \
            -> Tuple[Iterable[Tuple[str, Optional[str], Sequence[bytes]]],
                     Optional[SelectedMailbox]]:
        delimiter = self.mailbox_set.delimiter
        if filter_:
            if subscribed:
                list_tree = await self.mailbox_set.list_subscribed()
            else:
                list_tree = await self.mailbox_set.list_mailboxes()
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
            -> Tuple[ObjectId, Optional[SelectedMailbox]]:
        mailbox_id = await self.mailbox_set.add_mailbox(name)
        return mailbox_id, await self._load_updates(selected, None)

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
        await self.mailbox_set.set_subscribed(name, True)
        return await self._load_updates(selected, None)

    async def unsubscribe(self, name: str, selected: SelectedMailbox = None) \
            -> Optional[SelectedMailbox]:
        await self.mailbox_set.set_subscribed(name, False)
        return await self._load_updates(selected, None)

    async def append_messages(self, name: str,
                              messages: Sequence[AppendMessage],
                              selected: SelectedMailbox = None) \
            -> Tuple[AppendUid, Optional[SelectedMailbox]]:
        mbx = await self.mailbox_set.get_mailbox(name, try_create=True)
        if mbx.readonly:
            raise MailboxReadOnly(name)
        dest_selected = self._pick_selected(selected, mbx)
        uids: List[int] = []
        for append_msg in messages:
            msg = await mbx.add(append_msg, recent=not dest_selected)
            if dest_selected:
                dest_selected.session_flags.add_recent(msg.uid)
            uids.append(msg.uid)
        mbx.selected_set.updated.set()
        return (AppendUid(mbx.uid_validity, uids),
                await self._load_updates(selected, mbx))

    async def select_mailbox(self, name: str, readonly: bool = False) \
            -> Tuple[MailboxSnapshot, SelectedMailbox]:
        mbx = await self.mailbox_set.get_mailbox(name)
        selected = SelectedMailbox(mbx.mailbox_id, readonly or mbx.readonly,
                                   PermanentFlags(mbx.permanent_flags),
                                   SessionFlags(mbx.session_flags),
                                   selected_set=mbx.selected_set,
                                   lookup=name)
        if not selected.readonly:
            await mbx.claim_recent(selected)
        snapshot = await mbx.snapshot()
        return snapshot, await mbx.update_selected(selected)

    async def check_mailbox(self, selected: SelectedMailbox, *,
                            wait_on: Event = None,
                            housekeeping: bool = False) -> SelectedMailbox:
        mbx = await self._get_selected(selected)
        if housekeeping:
            await shield(mbx.cleanup())
        if wait_on is not None:
            either_event = wait_on.or_event(mbx.selected_set.updated)
            await either_event.wait()
        return await mbx.update_selected(selected)

    async def fetch_messages(self, selected: SelectedMailbox,
                             sequence_set: SequenceSet, set_seen: bool) \
            -> Tuple[Iterable[Tuple[int, MessageT]], SelectedMailbox]:
        mbx = await self._get_selected(selected)
        ret = [(seq, msg) async for seq, msg
               in mbx.find(sequence_set, selected)]
        if not selected.readonly and set_seen:
            seen_set = frozenset([Seen])
            await mbx.update_flags([msg for _, msg in ret],
                                   seen_set, FlagOp.ADD)
            mbx.selected_set.updated.set()
        return ret, await mbx.update_selected(selected)

    async def search_mailbox(self, selected: SelectedMailbox,
                             keys: FrozenSet[SearchKey]) \
            -> Tuple[Iterable[Tuple[int, MessageT]], SelectedMailbox]:
        mbx = await self._get_selected(selected)
        req = FetchRequirement.reduce(key.requirement for key in keys)
        ret: List[Tuple[int, MessageT]] = []
        params = SearchParams(selected,
                              disabled=self.config.disable_search_keys)
        search = SearchCriteriaSet(keys, params)
        async for seq, msg in mbx.find(search.sequence_set, selected):
            msg_content = await msg.load_content(req)
            if search.matches(seq, msg, msg_content):
                ret.append((seq, msg))
        return ret, await mbx.update_selected(selected)

    async def expunge_mailbox(self, selected: SelectedMailbox,
                              uid_set: SequenceSet = None) -> SelectedMailbox:
        if selected.readonly:
            raise MailboxReadOnly()
        mbx = await self._get_selected(selected)
        if not uid_set:
            uid_set = SequenceSet.all(uid=True)
        expunge_uids = await mbx.find_deleted(uid_set, selected)
        await mbx.delete(expunge_uids)
        mbx.selected_set.updated.set()
        return await mbx.update_selected(selected)

    async def copy_messages(self, selected: SelectedMailbox,
                            sequence_set: SequenceSet,
                            mailbox: str) \
            -> Tuple[Optional[CopyUid], SelectedMailbox]:
        mbx = await self._get_selected(selected)
        dest = await self.mailbox_set.get_mailbox(mailbox, try_create=True)
        if dest.readonly:
            raise MailboxReadOnly(mailbox)
        dest_selected = self._pick_selected(selected, dest)
        uids: List[Tuple[int, int]] = []
        async for _, msg in mbx.find(sequence_set, selected):
            if not msg.expunged:
                source_uid = msg.uid
                loaded = await msg.load_content(FetchRequirement.CONTENT)
                append_msg = msg.copy(loaded)
                if append_msg is None:
                    continue
                msg = await dest.add(append_msg, recent=not dest_selected,
                                     email_id=msg.email_id,
                                     thread_id=msg.thread_id)
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
            raise MailboxReadOnly()
        mbx = await self._get_selected(selected)
        permanent_flags = selected.permanent_flags & flag_set
        messages: List[Tuple[int, MessageT]] = []
        async for msg_seq, msg in mbx.find(sequence_set, selected):
            if not msg.expunged:
                selected.session_flags.update(msg.uid, flag_set, mode)
            messages.append((msg_seq, msg))
        await mbx.update_flags([msg for _, msg in messages],
                               permanent_flags, mode)
        mbx.selected_set.updated.set()
        return messages, await mbx.update_selected(selected)
