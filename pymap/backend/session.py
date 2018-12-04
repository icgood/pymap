
from typing import overload, Generic, Tuple, Optional, FrozenSet, Iterable, \
    Sequence, List

from pymap.concurrent import Event, TimeoutError
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

from .mailbox import MailboxDataInterface, MailboxSetInterface, Message, \
    MailboxDataT_co
from .util import asyncenumerate

__all__ = ['BaseSession']


class BaseSession(Generic[MailboxDataT_co], SessionInterface):
    """Base implementation of
    :class:`~pymap.interfaces.session.SessionInterface` intended for use by
    most backends.

    Args:
        mailbox_set: Manages the set of mailboxes available to the
            authenticated user.

    """

    def __init__(self, mailbox_set: MailboxSetInterface[MailboxDataT_co]) \
            -> None:
        super().__init__()
        self.mailbox_set = mailbox_set

    @overload
    async def _load_updates(self, selected: SelectedMailbox,
                            mbx: MailboxDataInterface) -> SelectedMailbox:
        ...

    @overload  # noqa
    async def _load_updates(self, selected: Optional[SelectedMailbox],
                            mbx: Optional[MailboxDataInterface]) \
            -> Optional[SelectedMailbox]:
        ...

    async def _load_updates(self, selected, mbx):  # noqa
        if selected:
            if not mbx or selected.name != mbx.name:
                try:
                    mbx = await self.mailbox_set.get_mailbox(selected.name)
                except MailboxNotFound:
                    selected.set_deleted()
                    return selected
            selected.uid_validity = mbx.uid_validity
            selected.next_uid = mbx.next_uid
            async for uid, msg in mbx.items():
                selected.add_messages((uid, frozenset(msg.permanent_flags)))
        return selected

    @classmethod
    def _find_selected(cls, selected: Optional[SelectedMailbox],
                       mbx: MailboxDataInterface) -> Optional[SelectedMailbox]:
        if selected and selected.name == mbx.name:
            return selected
        return mbx.selected_set.any_selected

    @classmethod
    async def _wait_for_updates(cls, mbx: MailboxDataInterface,
                                wait_on: Event) -> None:
        try:
            or_event = wait_on.or_event(mbx.selected_set.updated)
            await or_event.wait(timeout=10.0)
        except TimeoutError:
            pass

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
        return snapshot, await self._load_updates(selected, mbx)

    async def check_mailbox(self, selected: SelectedMailbox,
                            wait_on: Event = None,
                            housekeeping: bool = False) -> SelectedMailbox:
        mbx = await self.mailbox_set.get_mailbox(selected.name)
        if housekeeping:
            await mbx.cleanup()
        if wait_on:
            await self._wait_for_updates(mbx, wait_on)
        return await self._load_updates(selected, mbx)

    async def fetch_messages(self, selected: SelectedMailbox,
                             sequence_set: SequenceSet,
                             attributes: FrozenSet[FetchAttribute]) \
            -> Tuple[Iterable[Tuple[int, Message]], SelectedMailbox]:
        mbx = await self.mailbox_set.get_mailbox(selected.name)
        req = FetchRequirement.reduce({attr.requirement
                                       for attr in attributes})
        ret = [(seq, msg) async for seq, msg
               in mbx.find(sequence_set, selected, req) if not msg.expunged]
        if not selected.readonly and any(attr.set_seen for attr in attributes):
            for _, msg in ret:
                msg.permanent_flags.add(Seen)
            await mbx.save_flags(msg for _, msg in ret)
            mbx.selected_set.updated.set()
        return ret, await self._load_updates(selected, mbx)

    async def search_mailbox(self, selected: SelectedMailbox,
                             keys: FrozenSet[SearchKey]) \
            -> Tuple[Iterable[Tuple[int, Message]], SelectedMailbox]:
        mbx = await self.mailbox_set.get_mailbox(selected.name)
        ret: List[Tuple[int, Message]] = []
        snapshot = selected.snapshot
        params = SearchParams(selected, max_seq=snapshot.exists,
                              max_uid=snapshot.next_uid - 1)
        search = SearchCriteriaSet(keys, params)
        async for seq, msg in asyncenumerate(mbx.messages(), 1):
            if search.matches(seq, msg):
                ret.append((seq, msg))
        return ret, await self._load_updates(selected, mbx)

    async def expunge_mailbox(self, selected: SelectedMailbox,
                              uid_set: SequenceSet = None) -> SelectedMailbox:
        if selected.readonly:
            raise MailboxReadOnly(selected.name)
        mbx = await self.mailbox_set.get_mailbox(selected.name)
        if not uid_set:
            uid_set = SequenceSet.all(uid=True)
        expunge_uids: List[int] = []
        async for _, msg in mbx.find(uid_set, selected):
            if not msg.expunged and Deleted in msg.permanent_flags:
                expunge_uids.append(msg.uid)
        await mbx.delete(expunge_uids)
        mbx.selected_set.updated.set()
        return await self._load_updates(selected, mbx)

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
                await self._load_updates(selected, mbx))

    async def update_flags(self, selected: SelectedMailbox,
                           sequence_set: SequenceSet,
                           flag_set: FrozenSet[Flag],
                           mode: FlagOp = FlagOp.REPLACE) \
            -> Tuple[Iterable[Tuple[int, Message]], SelectedMailbox]:
        if selected.readonly:
            raise MailboxReadOnly(selected.name)
        mbx = await self.mailbox_set.get_mailbox(selected.name)
        permanent_flags = selected.permanent_flags & flag_set
        messages: List[Tuple[int, Message]] = []
        async for msg_seq, msg in mbx.find(sequence_set, selected):
            if not msg.expunged:
                msg.update_flags(permanent_flags, mode)
                selected.session_flags.update(msg.uid, flag_set, mode)
            messages.append((msg_seq, msg))
        await mbx.save_flags(msg for _, msg in messages)
        mbx.selected_set.updated.set()
        return messages, await self._load_updates(selected, mbx)
