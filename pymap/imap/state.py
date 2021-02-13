
from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable
from typing import Optional, Union, NoReturn

from pymap.bytes import MaybeBytes
from pymap.concurrent import Event
from pymap.config import IMAPConfig
from pymap.context import socket_info, connection_exit
from pymap.exceptions import NotSupportedError, CloseConnection
from pymap.fetch import MessageAttributes
from pymap.interfaces.login import LoginInterface
from pymap.interfaces.session import SessionInterface
from pymap.parsing.command import CommandAuth, CommandNonAuth, CommandSelect, \
    Command
from pymap.parsing.command.any import CapabilityCommand, LogoutCommand, \
    NoOpCommand
from pymap.parsing.command.nonauth import AuthenticateCommand, LoginCommand, \
    StartTLSCommand
from pymap.parsing.command.auth import AppendCommand, CreateCommand, \
    DeleteCommand, ListCommand, RenameCommand, SelectCommand, StatusCommand, \
    SubscribeCommand, UnsubscribeCommand
from pymap.parsing.command.select import CheckCommand, CloseCommand, \
    IdleCommand, ExpungeCommand, CopyCommand, MoveCommand, FetchCommand, \
    StoreCommand, SearchCommand
from pymap.parsing.commands import InvalidCommand
from pymap.parsing.primitives import List, Number
from pymap.parsing.response import ResponseOk, ResponseNo, ResponseBad, \
    ResponseCode, ResponsePreAuth, CommandResponse, UntaggedResponse
from pymap.parsing.response.code import Capability, PermanentFlags, UidNext, \
    UidValidity, Unseen, MailboxId
from pymap.parsing.response.specials import FlagsResponse, ExistsResponse, \
    RecentResponse, FetchResponse, ListResponse, LSubResponse, \
    SearchResponse, StatusResponse
from pymap.parsing.specials import StatusAttribute, FetchAttribute, FetchValue
from pymap.selected import SelectedMailbox
from pysasl import AuthenticationCredentials

__all__ = ['ConnectionState']

_AuthCommands = Union[AuthenticateCommand, LoginCommand]
_CommandRet = tuple[CommandResponse, Optional[SelectedMailbox]]
_CommandFunc = Callable[[Command], Awaitable[_CommandRet]]

_flags_attr = FetchAttribute(b'FLAGS')
_uid_attr = FetchAttribute(b'UID')


class ConnectionState:
    """Defines the state flow of the IMAP connection. Determines if a command
    can be processed at that point in the connection, and interacts with the
    backend plugin.

    """

    def __init__(self, login: LoginInterface, config: IMAPConfig) -> None:
        super().__init__()
        self.config = config
        self.auth = config.initial_auth
        self.login = login
        self._session: Optional[SessionInterface] = None
        self._selected: Optional[SelectedMailbox] = None
        self._capability = list(config.initial_capability)

    @property
    def session(self) -> SessionInterface:
        if self._session is None:
            raise RuntimeError()  # State checking should prevent this.
        return self._session

    @property
    def selected(self) -> SelectedMailbox:
        if self._selected is None:
            raise RuntimeError()  # State checking should prevent this.
        return self._selected

    @property
    def capability(self) -> Capability:
        if self._session:
            return Capability(self._capability)
        else:
            if self.auth.get_server(b'PLAIN') is None:
                logindisabled = [b'LOGINDISABLED']
            else:
                logindisabled = []
            return Capability(self._capability + logindisabled +
                              [b'AUTH=%b' % mech.name for mech in
                               self.auth.server_mechanisms])

    async def do_cleanup(self) -> None:
        try:
            await self.session.cleanup()
        except Exception:
            pass

    async def _login(self, creds: AuthenticationCredentials) \
            -> SessionInterface:
        stack = connection_exit.get()
        identity = await self.login.authenticate(creds)
        return await stack.enter_async_context(identity.new_session())

    async def do_greeting(self) -> CommandResponse:
        preauth_creds = self.config.preauth_credentials
        if preauth_creds:
            self._session = await self._login(preauth_creds)
        elif socket_info.get().from_localhost:
            self.auth = self.config.tls_auth
        resp_cls = ResponsePreAuth if preauth_creds else ResponseOk
        return resp_cls(b'*', self.config.greeting, self.capability)

    async def do_authenticate(self, cmd: _AuthCommands,
                              creds: Optional[AuthenticationCredentials]) \
            -> CommandResponse:
        if not creds:
            return ResponseNo(cmd.tag, b'Invalid authentication mechanism.')
        self._session = await self._login(creds)
        self._capability.extend(self.config.login_capability)
        return ResponseOk(cmd.tag, b'Authentication successful.',
                          self.capability)

    async def do_login(self, cmd: LoginCommand) -> _CommandRet:
        if b'LOGINDISABLED' in self.capability:
            raise NotSupportedError('LOGIN is disabled.')
        creds = AuthenticationCredentials(
            cmd.userid.decode('utf-8', 'surrogateescape'),
            cmd.password.decode('utf-8', 'surrogateescape'))
        return await self.do_authenticate(cmd, creds), None

    async def do_starttls(self, cmd: StartTLSCommand) -> _CommandRet:
        try:
            self._capability.remove(b'STARTTLS')
        except ValueError:
            raise NotSupportedError('STARTTLS not available.')
        self.auth = self.config.tls_auth
        return ResponseOk(cmd.tag, b'Ready to handshake.'), None

    async def do_capability(self, cmd: CapabilityCommand) -> _CommandRet:
        response = ResponseOk(cmd.tag, b'Capabilities listed.')
        response.add_untagged(UntaggedResponse(self.capability.string))
        return response, None

    async def do_noop(self, cmd: NoOpCommand) -> _CommandRet:
        updates = None
        if self._selected and self._session:
            updates = await self.session.check_mailbox(self.selected)
        return ResponseOk(cmd.tag, cmd.command + b' completed.'), updates

    async def do_select(self, cmd: SelectCommand) -> _CommandRet:
        self._selected = None
        mailbox, updates = await self.session.select_mailbox(
            cmd.mailbox, cmd.readonly)
        if updates.readonly:
            num_recent = mailbox.recent
            resp = ResponseOk(cmd.tag, b'Selected mailbox.',
                              ResponseCode.of(b'READ-ONLY'))
            resp.add_untagged_ok(b'Read-only mailbox.', PermanentFlags([]))
        else:
            num_recent = updates.session_flags.recent
            resp = ResponseOk(cmd.tag, b'Selected mailbox.',
                              ResponseCode.of(b'READ-WRITE'))
            resp.add_untagged_ok(b'Flags permitted.',
                                 PermanentFlags(mailbox.permanent_flags))
        messages = updates.messages
        resp.add_untagged(FlagsResponse(mailbox.flags))
        resp.add_untagged(ExistsResponse(messages.exists))
        resp.add_untagged(RecentResponse(num_recent))
        resp.add_untagged_ok(b'Predicted next UID.',
                             UidNext(mailbox.next_uid))
        resp.add_untagged_ok(b'UIDs valid.',
                             UidValidity(mailbox.uid_validity))
        if mailbox.first_unseen:
            resp.add_untagged_ok(b'First unseen message.',
                                 Unseen(mailbox.first_unseen))
        resp.add_untagged_ok(b'Object ID.', MailboxId(mailbox.mailbox_id))
        return resp, updates

    async def do_create(self, cmd: CreateCommand) -> _CommandRet:
        if cmd.mailbox == 'INBOX':
            return ResponseNo(cmd.tag, b'Cannot create INBOX.'), None
        mailbox_id, updates = await self.session.create_mailbox(
            cmd.mailbox, selected=self._selected)
        return ResponseOk(cmd.tag, cmd.command + b' completed.',
                          MailboxId(mailbox_id)), updates

    async def do_delete(self, cmd: DeleteCommand) -> _CommandRet:
        if cmd.mailbox == 'INBOX':
            return ResponseNo(cmd.tag, b'Cannot delete INBOX.'), None
        updates = await self.session.delete_mailbox(
            cmd.mailbox, selected=self._selected)
        return ResponseOk(cmd.tag, cmd.command + b' completed.'), updates

    async def do_rename(self, cmd: RenameCommand) -> _CommandRet:
        if cmd.to_mailbox == 'INBOX':
            return ResponseNo(cmd.tag, b'Cannot rename to INBOX.'), None
        updates = await self.session.rename_mailbox(
            cmd.from_mailbox, cmd.to_mailbox, selected=self._selected)
        return ResponseOk(cmd.tag, cmd.command + b' completed.'), updates

    async def do_status(self, cmd: StatusCommand) -> _CommandRet:
        mailbox, updates = await self.session.get_mailbox(
            cmd.mailbox, selected=self._selected)
        data: dict[StatusAttribute, MaybeBytes] = {}
        for attr in cmd.status_list:
            if attr == b'MESSAGES':
                data[attr] = Number(mailbox.exists)
            elif attr == b'RECENT':
                if updates and updates.mailbox_id == mailbox.mailbox_id:
                    data[attr] = Number(updates.session_flags.recent)
                else:
                    data[attr] = Number(mailbox.recent)
            elif attr == b'UNSEEN':
                data[attr] = Number(mailbox.unseen)
            elif attr == b'UIDNEXT':
                data[attr] = Number(mailbox.next_uid)
            elif attr == b'UIDVALIDITY':
                data[attr] = Number(mailbox.uid_validity)
            elif attr == b'MAILBOXID':
                data[attr] = mailbox.mailbox_id.parens
        resp = ResponseOk(cmd.tag, cmd.command + b' completed.')
        resp.add_untagged(StatusResponse(cmd.mailbox, data))
        return resp, updates

    async def do_append(self, cmd: AppendCommand) -> _CommandRet:
        if len(cmd.messages) > 1 and b'MULTIAPPEND' not in self.capability:
            raise NotSupportedError('MULTIAPPEND is disabled.')
        if cmd.cancelled:
            return ResponseNo(cmd.tag, b'APPEND cancelled.'), None
        if cmd.error:
            raise cmd.error
        append_uid, updates = await self.session.append_messages(
            cmd.mailbox, cmd.messages, selected=self._selected)
        resp = ResponseOk(cmd.tag, cmd.command + b' completed.', append_uid)
        return resp, updates

    async def do_subscribe(self, cmd: SubscribeCommand) -> _CommandRet:
        updates = await self.session.subscribe(
            cmd.mailbox, selected=self._selected)
        return ResponseOk(cmd.tag, cmd.command + b' completed.'), updates

    async def do_unsubscribe(self, cmd: UnsubscribeCommand) -> _CommandRet:
        updates = await self.session.unsubscribe(
            cmd.mailbox, selected=self._selected)
        return ResponseOk(cmd.tag, cmd.command + b' completed.'), updates

    async def do_list(self, cmd: ListCommand) -> _CommandRet:
        mailboxes, updates = await self.session.list_mailboxes(
            cmd.ref_name, cmd.filter, subscribed=cmd.only_subscribed,
            selected=self._selected)
        resp = ResponseOk(cmd.tag, cmd.command + b' completed.')
        resp_type = LSubResponse if cmd.only_subscribed else ListResponse
        for name, sep, attrs in mailboxes:
            resp.add_untagged(resp_type(name, sep, attrs))
        return resp, updates

    async def do_check(self, cmd: CheckCommand) -> _CommandRet:
        updates = await self.session.check_mailbox(
            self.selected, housekeeping=True)
        return ResponseOk(cmd.tag, cmd.command + b' completed.'), updates

    async def do_close(self, cmd: CloseCommand) -> _CommandRet:
        await self.session.expunge_mailbox(self.selected)
        self._selected = None
        return ResponseOk(cmd.tag, cmd.command + b' completed.'), None

    async def do_expunge(self, cmd: ExpungeCommand) -> _CommandRet:
        updates = await self.session.expunge_mailbox(
            self.selected, cmd.uid_set)
        resp = ResponseOk(cmd.tag, cmd.command + b' completed.')
        return resp, updates

    async def do_copy(self, cmd: CopyCommand) -> _CommandRet:
        copy_uid, updates = await self.session.copy_messages(
            self.selected, cmd.sequence_set, cmd.mailbox)
        resp = ResponseOk(cmd.tag, cmd.command + b' completed.', copy_uid)
        return resp, updates

    async def do_move(self, cmd: MoveCommand) -> _CommandRet:
        copy_uid, updates = await self.session.move_messages(
            self.selected, cmd.sequence_set, cmd.mailbox)
        resp = ResponseOk(cmd.tag, cmd.command + b' completed.')
        resp.add_untagged_ok(b'Moved.', copy_uid)
        return resp, updates

    async def do_fetch(self, cmd: FetchCommand) -> _CommandRet:
        if not cmd.uid:
            self.selected.hide_expunged = True
        set_seen = not self.selected.readonly and \
            any(attr.set_seen for attr in cmd.attributes)
        messages, updates = await self.session.fetch_messages(
            self.selected, cmd.sequence_set, set_seen)
        resp = ResponseOk(cmd.tag, cmd.command + b' completed.')
        for msg_seq, msg in messages:
            if msg.expunged:
                resp.code = ResponseCode.of(b'EXPUNGEISSUED')
            msg_attrs = MessageAttributes(msg, self.selected, cmd.attributes)
            fetch_resp = FetchResponse(msg_seq, msg_attrs,
                                       writing_hook=msg_attrs.load_hook())
            resp.add_untagged(fetch_resp)
        return resp, updates

    async def do_search(self, cmd: SearchCommand) -> _CommandRet:
        if not cmd.uid:
            self.selected.hide_expunged = True
        messages, updates = await self.session.search_mailbox(
            self.selected, cmd.keys)
        resp = ResponseOk(cmd.tag, cmd.command + b' completed.')
        msg_ids: list[int] = []
        for msg_seq, msg in messages:
            if msg.expunged:
                resp.code = ResponseCode.of(b'EXPUNGEISSUED')
            if cmd.uid:
                msg_ids.append(msg.uid)
            else:
                msg_ids.append(msg_seq)
        resp.add_untagged(SearchResponse(msg_ids))
        return resp, updates

    async def do_store(self, cmd: StoreCommand) -> _CommandRet:
        if not cmd.uid:
            self.selected.hide_expunged = True
        if cmd.silent:
            self.selected.silence(cmd.sequence_set, cmd.flag_set, cmd.mode)
        messages, updates = await self.session.update_flags(
            self.selected, cmd.sequence_set, cmd.flag_set, cmd.mode)
        resp = ResponseOk(cmd.tag, cmd.command + b' completed.')
        session_flags = self.selected.session_flags
        for msg_seq, msg in messages:
            if msg.expunged:
                resp.code = ResponseCode.of(b'EXPUNGEISSUED')
            elif cmd.silent:
                continue
            flags = msg.get_flags(session_flags)
            fetch_data: list[FetchValue] = [
                FetchValue.of(_flags_attr, List(flags, sort=True))]
            if cmd.uid:
                fetch_data.append(
                    FetchValue.of(_uid_attr, Number(msg.uid)))
            resp.add_untagged(FetchResponse(msg_seq, fetch_data))
        return resp, updates

    async def do_idle(self, cmd: IdleCommand) -> _CommandRet:
        if b'IDLE' not in self.capability:
            raise NotSupportedError('IDLE is disabled.')
        return ResponseOk(cmd.tag, cmd.command + b' completed.'), None

    @classmethod
    async def do_logout(cls, cmd: LogoutCommand) -> NoReturn:
        raise CloseConnection()

    async def receive_updates(self, cmd: IdleCommand, done: Event) \
            -> Iterable[UntaggedResponse]:
        selected = await self.session.check_mailbox(
            self.selected, wait_on=done)
        self._selected, untagged = selected.fork(cmd)
        return untagged

    @classmethod
    def _get_func_name(cls, cmd: Command) -> str:
        cmd_type = type(cmd)
        while cmd_type.delegate:
            cmd_type = cmd_type.delegate
        cmd_str = str(cmd_type.command, 'ascii').lower()
        return 'do_' + cmd_str

    async def do_command(self, cmd: Command) -> CommandResponse:
        if isinstance(cmd, InvalidCommand):
            return ResponseBad(cmd.tag, cmd.message)
        elif self._session and isinstance(cmd, CommandNonAuth):
            msg = cmd.command + b': Already authenticated.'
            return ResponseBad(cmd.tag, msg)
        elif not self._session and isinstance(cmd, CommandAuth):
            msg = cmd.command + b': Must authenticate first.'
            return ResponseBad(cmd.tag, msg)
        elif not self._selected and isinstance(cmd, CommandSelect):
            msg = cmd.command + b': Must select a mailbox first.'
            return ResponseBad(cmd.tag, msg)
        func_name = self._get_func_name(cmd)
        try:
            func: _CommandFunc = getattr(self, func_name)
        except AttributeError:
            return ResponseNo(cmd.tag, cmd.command + b': Not Implemented')
        response, selected = await func(cmd)
        if selected is not None:
            self._selected, untagged = selected.fork(cmd)
            response.add_untagged(*untagged)
        return response
