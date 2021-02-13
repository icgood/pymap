
from __future__ import annotations

from abc import abstractmethod
from asyncio import shield
from collections.abc import Iterable, Sequence
from typing import Generic, Optional

from pymap.concurrent import Event
from pymap.config import IMAPConfig
from pymap.exceptions import MailboxNotFound, MailboxConflict, MailboxReadOnly
from pymap.flags import FlagOp, SessionFlags, PermanentFlags
from pymap.interfaces.filter import FilterSetInterface
from pymap.interfaces.message import MessageT
from pymap.interfaces.session import SessionInterface
from pymap.mailbox import MailboxSnapshot
from pymap.parsing.message import AppendMessage
from pymap.parsing.specials import SequenceSet, SearchKey, ObjectId, \
    FetchRequirement
from pymap.parsing.specials.flag import Flag, Seen
from pymap.parsing.response.code import AppendUid, CopyUid
from pymap.search import SearchParams, SearchCriteriaSet
from pymap.selected import SelectedMailbox

from .mailbox import MailboxDataInterface, MailboxSetInterface

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

    def close(self) -> None:
        pass

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

    async def _get_mailbox(self, name: str, *, try_create: bool = False) \
            -> MailboxDataInterface[MessageT]:
        try:
            return await self.mailbox_set.get_mailbox(name)
        except KeyError as exc:
            raise MailboxNotFound(name, try_create=try_create) from exc

    async def _get_selected(self, selected: SelectedMailbox) \
            -> MailboxDataInterface[MessageT]:
        return await self._get_mailbox(selected.lookup)

    async def list_mailboxes(self, ref_name: str, filter_: str,
                             subscribed: bool = False,
                             selected: SelectedMailbox = None) \
            -> tuple[Iterable[tuple[str, Optional[str], Sequence[bytes]]],
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
            -> tuple[MailboxSnapshot, Optional[SelectedMailbox]]:
        try:
            mbx = await self.mailbox_set.get_mailbox(name)
        except KeyError as exc:
            raise MailboxNotFound(name) from exc
        snapshot = await mbx.snapshot()
        return snapshot, await self._load_updates(selected, mbx)

    async def create_mailbox(self, name: str,
                             selected: SelectedMailbox = None) \
            -> tuple[ObjectId, Optional[SelectedMailbox]]:
        try:
            mailbox_id = await self.mailbox_set.add_mailbox(name)
        except ValueError as exc:
            raise MailboxConflict(name) from exc
        return mailbox_id, await self._load_updates(selected, None)

    async def delete_mailbox(self, name: str,
                             selected: SelectedMailbox = None) \
            -> Optional[SelectedMailbox]:
        try:
            await self.mailbox_set.delete_mailbox(name)
        except KeyError as exc:
            raise MailboxNotFound(name) from exc
        return await self._load_updates(selected, None)

    async def rename_mailbox(self, before_name: str, after_name: str,
                             selected: SelectedMailbox = None) \
            -> Optional[SelectedMailbox]:
        try:
            await self.mailbox_set.rename_mailbox(before_name, after_name)
        except KeyError as exc:
            raise MailboxNotFound(before_name) from exc
        except ValueError as exc:
            raise MailboxConflict(after_name) from exc
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
            -> tuple[AppendUid, Optional[SelectedMailbox]]:
        mbx = await self._get_mailbox(name, try_create=True)
        if mbx.readonly:
            raise MailboxReadOnly(name)
        dest_selected = self._pick_selected(selected, mbx)
        uids: list[int] = []
        for append_msg in messages:
            msg = await mbx.append(append_msg, recent=not dest_selected)
            if dest_selected:
                dest_selected.session_flags.add_recent(msg.uid)
            uids.append(msg.uid)
        return (AppendUid(mbx.uid_validity, uids),
                await self._load_updates(selected, mbx))

    async def select_mailbox(self, name: str, readonly: bool = False) \
            -> tuple[MailboxSnapshot, SelectedMailbox]:
        mbx = await self._get_mailbox(name)
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
        return await mbx.update_selected(selected, wait_on=wait_on)

    async def fetch_messages(self, selected: SelectedMailbox,
                             sequence_set: SequenceSet, set_seen: bool) \
            -> tuple[Iterable[tuple[int, MessageT]], SelectedMailbox]:
        mbx = await self._get_selected(selected)
        ret: list[tuple[int, MessageT]] = []
        for seq, cached_msg in selected.messages.get_all(sequence_set):
            if set_seen:
                msg = await mbx.update(cached_msg.uid, cached_msg,
                                       frozenset({Seen}), FlagOp.ADD)
            else:
                msg = await mbx.get(cached_msg.uid, cached_msg)
            if msg is not None:
                ret.append((seq, msg))
        return ret, await mbx.update_selected(selected)

    async def search_mailbox(self, selected: SelectedMailbox,
                             keys: frozenset[SearchKey]) \
            -> tuple[Iterable[tuple[int, MessageT]], SelectedMailbox]:
        mbx = await self._get_selected(selected)
        req = FetchRequirement.reduce(key.requirement for key in keys)
        ret: list[tuple[int, MessageT]] = []
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
        if uid_set is None:
            uid_set = SequenceSet.all(uid=True)
        expunge_uids = await mbx.find_deleted(uid_set, selected)
        await mbx.delete(expunge_uids)
        return await mbx.update_selected(selected)

    async def copy_messages(self, selected: SelectedMailbox,
                            sequence_set: SequenceSet,
                            mailbox: str) \
            -> tuple[Optional[CopyUid], SelectedMailbox]:
        mbx = await self._get_selected(selected)
        dest = await self._get_mailbox(mailbox, try_create=True)
        if dest.readonly:
            raise MailboxReadOnly(mailbox)
        dest_selected = self._pick_selected(selected, dest)
        uids: list[tuple[int, int]] = []
        for _, source_uid in selected.messages.get_uids(sequence_set):
            dest_uid = await mbx.copy(source_uid, dest,
                                      recent=not dest_selected)
            if dest_uid is not None:
                if dest_selected:
                    dest_selected.session_flags.add_recent(dest_uid)
                uids.append((source_uid, dest_uid))
        if not uids:
            copy_uid: Optional[CopyUid] = None
        else:
            copy_uid = CopyUid(dest.uid_validity, uids)
        return (copy_uid, await mbx.update_selected(selected))

    async def move_messages(self, selected: SelectedMailbox,
                            sequence_set: SequenceSet,
                            mailbox: str) \
            -> tuple[Optional[CopyUid], SelectedMailbox]:
        mbx = await self._get_selected(selected)
        dest = await self._get_mailbox(mailbox, try_create=True)
        if dest.readonly:
            raise MailboxReadOnly(mailbox)
        dest_selected = self._pick_selected(selected, dest)
        uids: list[tuple[int, int]] = []
        for _, source_uid in selected.messages.get_uids(sequence_set):
            dest_uid = await mbx.move(source_uid, dest,
                                      recent=not dest_selected)
            if dest_uid is not None:
                if dest_selected:
                    dest_selected.session_flags.add_recent(dest_uid)
                uids.append((source_uid, dest_uid))
        if not uids:
            copy_uid: Optional[CopyUid] = None
        else:
            copy_uid = CopyUid(dest.uid_validity, uids)
        return (copy_uid, await mbx.update_selected(selected))

    async def update_flags(self, selected: SelectedMailbox,
                           sequence_set: SequenceSet,
                           flag_set: frozenset[Flag],
                           mode: FlagOp = FlagOp.REPLACE) \
            -> tuple[Iterable[tuple[int, MessageT]], SelectedMailbox]:
        if selected.readonly:
            raise MailboxReadOnly()
        mbx = await self._get_selected(selected)
        permanent_flags = selected.permanent_flags & flag_set
        messages: list[tuple[int, MessageT]] = []
        for seq, cached_msg in selected.messages.get_all(sequence_set):
            uid = cached_msg.uid
            msg = await mbx.update(uid, cached_msg, permanent_flags, mode)
            if not msg.expunged:
                selected.session_flags.update(uid, flag_set, mode)
            messages.append((seq, msg))
        return messages, await mbx.update_selected(selected)
