"""Defines the state flow of the IMAP connection. Determines if a command
can be processed at that point in the connection, and interacts with the
backend plugin.

"""

from collections import OrderedDict
from socket import getfqdn
from typing import Optional, Any, Dict, Callable, Union, Tuple, Awaitable, \
    AsyncIterable

from pysasl import AuthenticationCredentials

from .concurrent import Event
from .config import IMAPConfig
from .exceptions import CommandNotAllowed, CloseConnection
from .interfaces.session import SessionInterface, LoginProtocol
from .parsing.command import CommandAuth, CommandNonAuth, CommandSelect, \
    Command
from .parsing.command.any import CapabilityCommand, LogoutCommand, \
    NoOpCommand
from .parsing.command.nonauth import AuthenticateCommand, LoginCommand, \
    StartTLSCommand
from .parsing.command.auth import AppendCommand, CreateCommand, \
    DeleteCommand, ExamineCommand, ListCommand, LSubCommand, \
    RenameCommand, SelectCommand, StatusCommand, SubscribeCommand, \
    UnsubscribeCommand
from .parsing.command.select import CheckCommand, CloseCommand, IdleCommand, \
    ExpungeCommand, CopyCommand, FetchCommand, StoreCommand, SearchCommand
from .parsing.primitives import ListP, Number, String, Nil
from .parsing.response import Response, ResponseOk, ResponseNo, ResponseBad, \
        ResponsePreAuth
from .parsing.response.code import Capability, PermanentFlags, ReadOnly, \
    UidNext, UidValidity, Unseen, ReadWrite
from .parsing.response.specials import FlagsResponse, ExistsResponse, \
    RecentResponse, FetchResponse, ListResponse, LSubResponse, \
    SearchResponse, StatusResponse
from .parsing.specials import DateTime, FetchAttribute
from .sockinfo import SocketInfo
from .proxy import ExecutorProxy
from .selected import SelectedMailbox

__all__ = ['ConnectionState']

_AuthCommands = Union[AuthenticateCommand, LoginCommand]
_CommandFunc = Callable[[Command],
                        Awaitable[Tuple[Response, SelectedMailbox]]]

fqdn = getfqdn().encode('ascii')


class ConnectionState:
    """Defines the interaction with the backend plugin."""

    def __init__(self, login: LoginProtocol, config: IMAPConfig) -> None:
        super().__init__()
        self.config = config
        self.ssl_context = config.ssl_context
        self._login = login
        self._session: Optional[SessionInterface] = None
        self._selected: Optional[SelectedMailbox] = None
        self._capability = list(config.initial_capability)
        self._proxy = ExecutorProxy(config.executor)
        self.auth = config.initial_auth

    @property
    def login(self) -> LoginProtocol:
        if self._proxy:
            return self._proxy.wrap_login(self._login)
        else:
            return self._login

    @property
    def session(self) -> SessionInterface:
        if self._session is None:
            raise RuntimeError()  # State checking should prevent this.
        if self._proxy:
            return self._proxy.wrap_session(self._session)
        else:
            return self._session

    @property
    def selected(self) -> SelectedMailbox:
        if self._selected is None:
            raise RuntimeError()  # State checking should prevent this.
        return self._selected

    @property
    def capability(self) -> Capability:
        if self._session:
            login_capability = list(self.config.login_capability)
            return Capability(self._capability + login_capability)
        else:
            return Capability(self._capability +
                              [b'AUTH=%b' % mech.name for mech in
                               self.auth.server_mechanisms])

    async def do_greeting(self, sock_info: SocketInfo) -> Response:
        preauth_creds = self.config.preauth_credentials
        if preauth_creds:
            self._session = await self.login(
                preauth_creds, self.config, sock_info)
        resp_cls = ResponsePreAuth if preauth_creds else ResponseOk
        return resp_cls(b'*', b'Server ready ' + fqdn, self.capability)

    async def do_authenticate(self, cmd: _AuthCommands, sock_info: SocketInfo,
                              creds: Optional[AuthenticationCredentials]):
        if not creds:
            return ResponseNo(cmd.tag, b'Invalid authentication mechanism.')
        self._session = await self.login(creds, self.config, sock_info)
        return ResponseOk(cmd.tag, b'Authentication successful.',
                          self.capability)

    async def do_login(self, cmd: LoginCommand, sock_info: SocketInfo,
                       creds: AuthenticationCredentials) -> Response:
        if b'LOGINDISABLED' in self.capability:
            raise CommandNotAllowed(b'LOGIN is disabled.')
        return await self.do_authenticate(cmd, sock_info, creds)

    async def do_starttls(self, cmd: StartTLSCommand):
        if self.ssl_context is None:
            raise ValueError('ssl_context is None')
        try:
            self._capability.remove(b'STARTTLS')
        except ValueError:
            raise CommandNotAllowed(b'STARTTLS not available.')
        try:
            self._capability.remove(b'LOGINDISABLED')
        except ValueError:
            pass
        self.auth = self.config.starttls_auth
        return ResponseOk(cmd.tag, b'Ready to handshake.'), None

    async def do_capability(self, cmd: CapabilityCommand):
        response = ResponseOk(cmd.tag, b'Capabilities listed.')
        response.add_untagged(Response(b'*', self.capability.string))
        return response, None

    async def do_noop(self, cmd: NoOpCommand):
        updates = None
        if self._selected and self._session:
            updates = await self.session.check_mailbox(self.selected)
        return ResponseOk(cmd.tag, b'NOOP completed.'), updates

    async def _select_mailbox(self, cmd: SelectCommand, examine: bool):
        self._selected = None
        mailbox, updates = await self.session.select_mailbox(
            cmd.mailbox, examine)
        if updates.readonly:
            resp = ResponseOk(cmd.tag, b'Selected mailbox.', ReadOnly())
            resp.add_untagged_ok(b'Read-only mailbox.', PermanentFlags([]))
        else:
            resp = ResponseOk(cmd.tag, b'Selected mailbox.', ReadWrite())
            resp.add_untagged_ok(b'Flags permitted.',
                                 PermanentFlags(mailbox.permanent_flags))
        resp.add_untagged(FlagsResponse(mailbox.flags))
        resp.add_untagged(ExistsResponse(updates.exists))
        resp.add_untagged(RecentResponse(updates.recent))
        resp.add_untagged_ok(b'Predicted next UID.', UidNext(mailbox.next_uid))
        resp.add_untagged_ok(b'UIDs valid.',
                             UidValidity(mailbox.uid_validity))
        if mailbox.first_unseen:
            resp.add_untagged_ok(b'First unseen message.',
                                 Unseen(mailbox.first_unseen))
        return resp, updates

    async def do_select(self, cmd: SelectCommand):
        return await self._select_mailbox(cmd, False)

    async def do_examine(self, cmd: ExamineCommand):
        return await self._select_mailbox(cmd, True)

    async def do_create(self, cmd: CreateCommand):
        if cmd.mailbox == 'INBOX':
            return ResponseNo(cmd.tag, b'Cannot create INBOX.'), None
        updates = await self.session.create_mailbox(
            cmd.mailbox, selected=self._selected)
        return ResponseOk(cmd.tag, b'Mailbox created successfully.'), updates

    async def do_delete(self, cmd: DeleteCommand):
        if cmd.mailbox == 'INBOX':
            return ResponseNo(cmd.tag, b'Cannot delete INBOX.'), None
        updates = await self.session.delete_mailbox(
            cmd.mailbox, selected=self._selected)
        return ResponseOk(cmd.tag, b'Mailbox deleted successfully.'), updates

    async def do_rename(self, cmd: RenameCommand):
        if cmd.to_mailbox == 'INBOX':
            return ResponseNo(cmd.tag, b'Cannot rename to INBOX.'), None
        updates = await self.session.rename_mailbox(
            cmd.from_mailbox, cmd.to_mailbox, selected=self._selected)
        return ResponseOk(cmd.tag, b'Mailbox renamed successfully.'), updates

    async def do_status(self, cmd: StatusCommand):
        mailbox, updates = await self.session.get_mailbox(
            cmd.mailbox, selected=self._selected)
        data = OrderedDict()  # type: ignore
        for attr in cmd.status_list:
            if attr == b'MESSAGES':
                data[attr] = Number(mailbox.exists)
            elif attr == b'RECENT':
                data[attr] = Number(mailbox.recent)
            elif attr == b'UNSEEN':
                data[attr] = Number(mailbox.unseen)
            elif attr == b'UIDNEXT':
                data[attr] = Number(mailbox.next_uid)
            elif attr == b'UIDVALIDITY':
                data[attr] = Number(mailbox.uid_validity)
        resp = ResponseOk(cmd.tag, b'STATUS completed.')
        resp.add_untagged(StatusResponse(cmd.mailbox, data))
        return resp, updates

    async def do_append(self, cmd: AppendCommand):
        for msg in cmd.messages:
            if msg.message == b'':
                return ResponseNo(cmd.tag, b'APPEND cancelled.'), None
        append_uid, updates = await self.session.append_messages(
            cmd.mailbox, cmd.messages, selected=self._selected)
        return ResponseOk(cmd.tag, b'APPEND completed.', append_uid), updates

    async def do_subscribe(self, cmd: SubscribeCommand):
        updates = await self.session.subscribe(
            cmd.mailbox, selected=self._selected)
        return ResponseOk(cmd.tag, b'SUBSCRIBE completed.'), updates

    async def do_unsubscribe(self, cmd: UnsubscribeCommand):
        updates = await self.session.unsubscribe(
            cmd.mailbox, selected=self._selected)
        return ResponseOk(cmd.tag, b'UNSUBSCRIBE completed.'), updates

    async def do_list(self, cmd: ListCommand):
        mailboxes, updates = await self.session.list_mailboxes(
            cmd.ref_name, cmd.filter, selected=self._selected)
        resp = ResponseOk(cmd.tag, b'LIST completed.')
        for name, sep, attrs in mailboxes:
            resp.add_untagged(ListResponse(name, sep, attrs))
        return resp, updates

    async def do_lsub(self, cmd: LSubCommand):
        mailboxes, updates = await self.session.list_mailboxes(
            cmd.ref_name, cmd.filter, subscribed=True, selected=self._selected)
        resp = ResponseOk(cmd.tag, b'LSUB completed.')
        for name, sep, attrs in mailboxes:
            resp.add_untagged(LSubResponse(name, sep, attrs))
        return resp, updates

    async def do_check(self, cmd: CheckCommand):
        updates = await self.session.check_mailbox(
            self.selected, housekeeping=True)
        return ResponseOk(cmd.tag, b'CHECK completed.'), updates

    async def do_close(self, cmd: CloseCommand):
        await self.session.expunge_mailbox(self.selected)
        self._selected = None
        return ResponseOk(cmd.tag, b'CLOSE completed.'), None

    async def do_expunge(self, cmd: ExpungeCommand):
        updates = await self.session.expunge_mailbox(
            self.selected, cmd.uid_set)
        resp = ResponseOk(cmd.tag, b'EXPUNGE completed.')
        return resp, updates

    async def do_copy(self, cmd: CopyCommand):
        copy_uid, updates = await self.session.copy_messages(
            self.selected, cmd.sequence_set, cmd.mailbox)
        return ResponseOk(cmd.tag, b'COPY completed.', copy_uid), updates

    async def do_fetch(self, cmd: FetchCommand):
        messages, updates = await self.session.fetch_messages(
            self.selected, cmd.sequence_set, frozenset(cmd.attributes))
        resp = ResponseOk(cmd.tag, b'FETCH completed.')
        session_flags = self.selected.session_flags
        for msg_seq, msg in messages:
            fetch_data: Dict[FetchAttribute, Any] = OrderedDict()
            for attr in cmd.attributes:
                if attr.value == b'UID':
                    fetch_data[attr] = Number(msg.uid)
                elif attr.value == b'FLAGS':
                    flags = msg.get_flags(session_flags)
                    fetch_data[attr] = ListP(flags, sort=True)
                elif attr.value == b'INTERNALDATE':
                    if msg.internal_date:
                        fetch_data[attr] = DateTime(msg.internal_date)
                    else:
                        fetch_data[attr] = Nil()
                elif attr.value == b'ENVELOPE':
                    fetch_data[attr] = msg.get_envelope_structure()
                elif attr.value == b'BODYSTRUCTURE':
                    fetch_data[attr] = msg.get_body_structure().extended
                elif attr.value in (b'BODY', b'BODY.PEEK'):
                    if not attr.section:
                        fetch_data[attr] = msg.get_body_structure()
                    elif not attr.section.specifier:
                        fetch_data[attr] = String.build(msg.get_body(
                            attr.section.parts))
                    elif attr.section.specifier == b'TEXT':
                        fetch_data[attr] = String.build(msg.get_text(
                            attr.section.parts))
                    elif attr.section.specifier in (b'HEADER', b'MIME'):
                        fetch_data[attr] = String.build(msg.get_headers(
                            attr.section.parts))
                    elif attr.section.specifier == b'HEADER.FIELDS':
                        fetch_data[attr] = String.build(msg.get_headers(
                            attr.section.parts, attr.section.headers))
                    elif attr.section.specifier == b'HEADER.FIELDS.NOT':
                        fetch_data[attr] = String.build(msg.get_headers(
                            attr.section.parts, attr.section.headers, True))
                elif attr.value == b'RFC822':
                    fetch_data[attr] = String.build(msg.get_body())
                elif attr.value == b'RFC822.HEADER':
                    fetch_data[attr] = String.build(msg.get_headers())
                elif attr.value == b'RFC822.TEXT':
                    fetch_data[attr] = String.build(msg.get_text())
                elif attr.value == b'RFC822.SIZE':
                    fetch_data[attr] = Number(msg.get_size())
                elif attr.value in (b'BINARY', b'BINARY.PEEK'):
                    parts = attr.section.parts if attr.section else None
                    fetch_data[attr] = String.build(
                        msg.get_body(parts, True), True)
                elif attr.value == b'BINARY.SIZE':
                    parts = attr.section.parts if attr.section else None
                    fetch_data[attr] = Number(msg.get_size(parts, True))
            resp.add_untagged(FetchResponse(msg_seq, fetch_data))
        if not cmd.uid:
            self.selected.hide_expunged()
        return resp, updates

    async def do_search(self, cmd: SearchCommand):
        messages, updates = await self.session.search_mailbox(
            self.selected, cmd.keys)
        resp = ResponseOk(cmd.tag, b'SEARCH completed.')
        if cmd.uid:
            msg_ids = [msg.uid for _, msg in messages]
        else:
            msg_ids = [msg_seq for msg_seq, _ in messages]
        resp.add_untagged(SearchResponse(msg_ids))
        if not cmd.uid:
            self.selected.hide_expunged()
        return resp, updates

    async def do_store(self, cmd: StoreCommand):
        uids, updates = await self.session.update_flags(
            self.selected, cmd.sequence_set, cmd.flag_set, cmd.mode)
        resp = ResponseOk(cmd.tag, b'STORE completed.')
        if cmd.silent:
            self.selected.hide(*uids)
        if not cmd.uid:
            self.selected.hide_expunged()
        return resp, updates

    async def do_idle(self, cmd: IdleCommand):
        if b'IDLE' not in self.capability:
            raise CommandNotAllowed(b'IDLE is disabled.')
        return ResponseOk(cmd.tag, b'IDLE completed.'), None

    @classmethod
    async def do_logout(cls, cmd: LogoutCommand):
        raise CloseConnection()

    async def receive_updates(self, cmd: IdleCommand, done: Event) \
            -> AsyncIterable[Response]:
        while not done.is_set():
            selected = await self.session.check_mailbox(
                self.selected, wait_on=done)
            self._selected, untagged = selected.fork(cmd)
            for resp in untagged:
                yield resp

    @classmethod
    def _get_func_name(cls, cmd: Command) -> str:
        cmd_type = type(cmd)
        while cmd_type.delegate:
            cmd_type = cmd_type.delegate
        cmd_str = str(cmd_type.command, 'ascii').lower()
        return 'do_' + cmd_str

    async def do_command(self, cmd: Command):
        if self._session and isinstance(cmd, CommandNonAuth):
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
        if selected:
            self._selected, untagged = selected.fork(cmd)
            response.add_untagged(*untagged)
        return response
