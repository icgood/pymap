
from typing import overload, TypeVar, Generic, Tuple, Optional, \
    FrozenSet, Mapping, Iterable, Sequence, List

from pymap.concurrent import Event, TimeoutError
from pymap.exceptions import MailboxNotFound
from pymap.flags import FlagOp
from pymap.message import AppendMessage
from pymap.parsing.specials import SequenceSet, FetchAttribute, SearchKey
from pymap.parsing.specials.flag import Flag, Deleted, Recent
from pymap.parsing.response.code import AppendUid, CopyUid
from pymap.interfaces.session import SessionInterface
from pymap.search import SearchParams, SearchCriteriaSet
from pymap.selected import SelectedMailbox

from .mailbox import KeyValMessage, KeyValMailbox, MailboxSnapshot
from .util import asyncenumerate

__all__ = ['KeyValSession']

_Message = TypeVar('_Message', bound=KeyValMessage)
_Mailbox = TypeVar('_Mailbox', bound=KeyValMailbox)


class KeyValSession(Generic[_Mailbox, _Message],
                    SessionInterface[SelectedMailbox]):

    def __init__(self, inbox: _Mailbox) -> None:
        super().__init__()
        self.inbox = inbox

    def _get_mbx_selected(self, selected: Optional[SelectedMailbox],
                          mbx: _Mailbox) -> Optional[SelectedMailbox]:
        if selected and selected.name == mbx.name:
            return selected
        elif mbx.last_selected:
            return mbx.last_selected
        return None

    @overload
    async def _load_updates(self, selected: SelectedMailbox,
                            mbx: _Mailbox) -> SelectedMailbox:
        ...

    @overload  # noqa
    async def _load_updates(self, selected: Optional[SelectedMailbox],
                            mbx: Optional[_Mailbox]) \
            -> Optional[SelectedMailbox]:
        ...

    async def _load_updates(self, selected, mbx):  # noqa
        if selected:
            if not mbx or selected.name != mbx.name:
                try:
                    mbx = await self.inbox.get_mailbox(selected.name)
                except MailboxNotFound:
                    selected.set_deleted()
                    return selected
            selected.set_uid_validity(mbx.uid_validity)
            async for uid, msg in mbx.items():
                selected.add_messages((uid, msg.permanent_flags))
        return selected

    async def _wait_for_updates(self, mbx: _Mailbox, wait_on: Event) -> None:
        try:
            or_event = wait_on.or_event(mbx.updated)
            await or_event.wait(timeout=10.0)
        except TimeoutError:
            pass

    async def list_mailboxes(self, ref_name: str, filter_: str,
                             subscribed: bool = False,
                             selected: SelectedMailbox = None) \
            -> Tuple[Iterable[Tuple[str, bytes, Mapping[str, bool]]],
                     Optional[SelectedMailbox]]:
        if subscribed:
            mbx_names = ['INBOX'] + list(await self.inbox.list_subscribed())
        else:
            mbx_names = ['INBOX'] + list(await self.inbox.list_mailboxes())
        return ([(name, b'.', {}) for name in mbx_names],
                await self._load_updates(selected, None))

    async def get_mailbox(self, name: str, selected: SelectedMailbox = None) \
            -> Tuple[MailboxSnapshot, Optional[SelectedMailbox]]:
        mbx = await self.inbox.get_mailbox(name)
        snapshot = await mbx.snapshot()
        return snapshot, await self._load_updates(selected, mbx)

    async def create_mailbox(self, name: str,
                             selected: SelectedMailbox = None) \
            -> Optional[SelectedMailbox]:
        await self.inbox.add_mailbox(name)
        return await self._load_updates(selected, None)

    async def delete_mailbox(self, name: str,
                             selected: SelectedMailbox = None) \
            -> Optional[SelectedMailbox]:
        await self.inbox.remove_mailbox(name)
        return await self._load_updates(selected, None)

    async def rename_mailbox(self, before_name: str, after_name: str,
                             selected: SelectedMailbox = None) \
            -> Optional[SelectedMailbox]:
        await self.inbox.rename_mailbox(before_name, after_name)
        return await self._load_updates(selected, None)

    async def subscribe(self, name: str, selected: SelectedMailbox = None) \
            -> Optional[SelectedMailbox]:
        mbx = await self.inbox.get_mailbox('INBOX')
        await mbx.set_subscribed(name, True)
        return await self._load_updates(selected, mbx)

    async def unsubscribe(self, name: str, selected: SelectedMailbox = None) \
            -> Optional[SelectedMailbox]:
        mbx = await self.inbox.get_mailbox('INBOX')
        await mbx.set_subscribed(name, False)
        return await self._load_updates(selected, mbx)

    async def append_messages(self, name: str,
                              messages: Sequence[AppendMessage],
                              selected: SelectedMailbox = None) \
            -> Tuple[AppendUid, Optional[SelectedMailbox]]:
        mbx = await self.inbox.get_mailbox(name)
        mbx_selected = self._get_mbx_selected(selected, mbx)
        uids: List[int] = []
        for append_msg in messages:
            msg = mbx.parse_message(append_msg, not mbx_selected)
            msg = await mbx.add(msg)
            if mbx_selected:
                mbx_selected.session_flags.add_recent(msg.uid)
            uids.append(msg.uid)
        mbx.updated.set()
        return (AppendUid(mbx.uid_validity, uids),
                await self._load_updates(selected, mbx))

    async def select_mailbox(self, name: str, readonly: bool = False) \
            -> Tuple[MailboxSnapshot, SelectedMailbox]:
        mbx = await self.inbox.get_mailbox(name)
        selected = mbx.new_selected(readonly)
        if not readonly:
            recent_msgs: List[_Message] = []
            async for msg in mbx.messages():
                if Recent in msg.permanent_flags:
                    msg.permanent_flags.remove(Recent)
                    selected.session_flags.add_recent(msg.uid)
                    recent_msgs.append(msg)
            await mbx.save_flags(*recent_msgs)
        snapshot = await mbx.snapshot()
        return snapshot, await self._load_updates(selected, mbx)

    async def check_mailbox(self, selected: SelectedMailbox,
                            wait_on: Event = None,
                            housekeeping: bool = False) -> SelectedMailbox:
        mbx = await self.inbox.get_mailbox(selected.name)
        if housekeeping:
            await mbx.cleanup()
        if wait_on:
            await self._wait_for_updates(mbx, wait_on)
        return await self._load_updates(selected, mbx)

    async def fetch_messages(self, selected: SelectedMailbox,
                             sequences: SequenceSet,
                             attributes: FrozenSet[FetchAttribute]) \
            -> Tuple[Iterable[Tuple[int, _Message]], SelectedMailbox]:
        mbx = await self.inbox.get_mailbox(selected.name)
        ret: List[Tuple[int, _Message]] = []
        async for seq, msg in mbx.find(sequences):
            ret.append((seq, msg))
        return ret, await self._load_updates(selected, mbx)

    async def search_mailbox(self, selected: SelectedMailbox,
                             keys: FrozenSet[SearchKey]) \
            -> Tuple[Iterable[Tuple[int, _Message]], SelectedMailbox]:
        mbx = await self.inbox.get_mailbox(selected.name)
        ret: List[Tuple[int, _Message]] = []
        max_seq = await mbx.get_count()
        max_uid = await mbx.get_max_uid()
        params = SearchParams(selected, max_seq=max_seq, max_uid=max_uid)
        search = SearchCriteriaSet(keys, params)
        async for seq, msg in asyncenumerate(mbx.messages(), 1):
            if search.matches(seq, msg):
                ret.append((seq, msg))
        return ret, await self._load_updates(selected, mbx)

    async def expunge_mailbox(self, selected: SelectedMailbox,
                              uid_set: SequenceSet = None) -> SelectedMailbox:
        mbx = await self.inbox.get_mailbox(selected.name)
        if not uid_set:
            uid_set = SequenceSet.all(uid=True)
        expunge_uids: List[int] = []
        async for seq, msg in mbx.find(uid_set):
            if Deleted in msg.permanent_flags:
                expunge_uids.append(msg.uid)
        for uid in expunge_uids:
            selected.session_flags.remove(uid)
            await mbx.delete(uid)
        mbx.updated.set()
        return await self._load_updates(selected, mbx)

    async def copy_messages(self, selected: SelectedMailbox,
                            sequences: SequenceSet,
                            mailbox: str) \
            -> Tuple[Optional[CopyUid], SelectedMailbox]:
        mbx = await self.inbox.get_mailbox(selected.name)
        dest = await self.inbox.get_mailbox(mailbox)
        last_selected = dest.last_selected
        uids: List[Tuple[int, int]] = []
        async for seq, msg in mbx.find(sequences):
            source_uid = msg.uid
            msg = await dest.add(msg)
            if last_selected:
                last_selected.session_flags.add_recent(msg.uid)
            else:
                msg.permanent_flags.add(Recent)
            uids.append((source_uid, msg.uid))
        mbx.updated.set()
        return (CopyUid(dest.uid_validity, uids),
                await self._load_updates(selected, mbx))

    async def update_flags(self, selected: SelectedMailbox,
                           sequences: SequenceSet,
                           flag_set: FrozenSet[Flag],
                           mode: FlagOp = FlagOp.REPLACE) \
            -> Tuple[Iterable[int], SelectedMailbox]:
        mbx = await self.inbox.get_mailbox(selected.name)
        permanent_flags = flag_set & mbx.permanent_flags
        session_flags = flag_set & mbx.session_flags
        messages: List[_Message] = []
        async for _, msg in mbx.find(sequences):
            msg.update_flags(permanent_flags, mode)
            selected.session_flags.update(msg.uid, session_flags, mode)
            messages.append(msg)
        await mbx.save_flags(*messages)
        uids = [msg.uid for msg in messages]
        mbx.updated.set()
        return uids, await self._load_updates(selected, mbx)
