
from collections import OrderedDict
from socket import getfqdn
from typing import Optional, Dict, List, Callable, Union, Tuple, Awaitable, \
    Iterable

from pymap.bytes import MaybeBytes
from pymap.concurrent import Event
from pymap.config import IMAPConfig
from pymap.exceptions import CommandNotAllowed, CloseConnection
from pymap.interfaces.session import SessionInterface, LoginProtocol
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
    IdleCommand, ExpungeCommand, CopyCommand, FetchCommand, StoreCommand, \
    SearchCommand
from pymap.parsing.commands import InvalidCommand
from pymap.parsing.primitives import ListP, Number, LiteralString, Nil
from pymap.parsing.response import Response, ResponseOk, ResponseNo, \
    ResponseBad,  ResponseCode, ResponsePreAuth
from pymap.parsing.response.code import Capability, PermanentFlags, UidNext, \
    UidValidity, Unseen
from pymap.parsing.response.specials import FlagsResponse, ExistsResponse, \
    RecentResponse, FetchResponse, ListResponse, LSubResponse, \
    SearchResponse, StatusResponse
from pymap.parsing.specials import DateTime, FetchAttribute, StatusAttribute
from pymap.selected import SelectedMailbox
from pysasl import AuthenticationCredentials

__all__ = ['ConnectionState']

_AuthCommands = Union[AuthenticateCommand, LoginCommand]
_CommandFunc = Callable[[Command],
                        Awaitable[Tuple[Response, SelectedMailbox]]]

fqdn = getfqdn().encode('ascii')


class ConnectionState:
    """Defines the state flow of the IMAP connection. Determines if a command
    can be processed at that point in the connection, and interacts with the
    backend plugin.

    """

    def __init__(self, login: LoginProtocol, config: IMAPConfig) -> None:
        super().__init__()
        self.config = config
        self.ssl_context = config.ssl_context
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
            return Capability(self._capability +
                              [b'AUTH=%b' % mech.name for mech in
                               self.auth.server_mechanisms])

    async def do_greeting(self) -> Response:
        preauth_creds = self.config.preauth_credentials
        if preauth_creds:
            self._session = await self.login(preauth_creds, self.config)
        resp_cls = ResponsePreAuth if preauth_creds else ResponseOk
        return resp_cls(b'*', b'Server ready ' + fqdn, self.capability)

    async def do_authenticate(self, cmd: _AuthCommands,
                              creds: Optional[AuthenticationCredentials]):
        if not creds:
            return ResponseNo(cmd.tag, b'Invalid authentication mechanism.')
        self._session = await self.login(creds, self.config)
        self._capability.extend(self.config.login_capability)
        return ResponseOk(cmd.tag, b'Authentication successful.',
                          self.capability), None

    async def do_login(self, cmd: LoginCommand) -> Response:
        if b'LOGINDISABLED' in self.capability:
            raise CommandNotAllowed(b'LOGIN is disabled.')
        creds = AuthenticationCredentials(
            cmd.userid.decode('utf-8', 'surrogateescape'),
            cmd.password.decode('utf-8', 'surrogateescape'))
        return await self.do_authenticate(cmd, creds)

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
        return ResponseOk(cmd.tag, cmd.command + b' completed.'), updates

    async def do_select(self, cmd: SelectCommand):
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
                             UidValidity(updates.uid_validity))
        if mailbox.first_unseen:
            resp.add_untagged_ok(b'First unseen message.',
                                 Unseen(mailbox.first_unseen))
        return resp, updates

    async def do_create(self, cmd: CreateCommand):
        if cmd.mailbox == 'INBOX':
            return ResponseNo(cmd.tag, b'Cannot create INBOX.'), None
        updates = await self.session.create_mailbox(
            cmd.mailbox, selected=self._selected)
        return ResponseOk(cmd.tag, cmd.command + b' completed.'), updates

    async def do_delete(self, cmd: DeleteCommand):
        if cmd.mailbox == 'INBOX':
            return ResponseNo(cmd.tag, b'Cannot delete INBOX.'), None
        updates = await self.session.delete_mailbox(
            cmd.mailbox, selected=self._selected)
        return ResponseOk(cmd.tag, cmd.command + b' completed.'), updates

    async def do_rename(self, cmd: RenameCommand):
        if cmd.to_mailbox == 'INBOX':
            return ResponseNo(cmd.tag, b'Cannot rename to INBOX.'), None
        updates = await self.session.rename_mailbox(
            cmd.from_mailbox, cmd.to_mailbox, selected=self._selected)
        return ResponseOk(cmd.tag, cmd.command + b' completed.'), updates

    async def do_status(self, cmd: StatusCommand):
        mailbox, updates = await self.session.get_mailbox(
            cmd.mailbox, selected=self._selected)
        data: Dict[StatusAttribute, Number] = OrderedDict()
        for attr in cmd.status_list:
            if attr == b'MESSAGES':
                data[attr] = Number(mailbox.exists)
            elif attr == b'RECENT':
                if updates and updates.name == cmd.mailbox:
                    data[attr] = Number(updates.session_flags.recent)
                else:
                    data[attr] = Number(mailbox.recent)
            elif attr == b'UNSEEN':
                data[attr] = Number(mailbox.unseen)
            elif attr == b'UIDNEXT':
                data[attr] = Number(mailbox.next_uid)
            elif attr == b'UIDVALIDITY':
                data[attr] = Number(mailbox.uid_validity)
        resp = ResponseOk(cmd.tag, cmd.command + b' completed.')
        resp.add_untagged(StatusResponse(cmd.mailbox, data))
        return resp, updates

    async def do_append(self, cmd: AppendCommand):
        for msg in cmd.messages:
            if msg.message == b'':
                return ResponseNo(cmd.tag, b'APPEND cancelled.'), None
        append_uid, updates = await self.session.append_messages(
            cmd.mailbox, cmd.messages, selected=self._selected)
        resp = ResponseOk(cmd.tag, cmd.command + b' completed.', append_uid)
        return resp, updates

    async def do_subscribe(self, cmd: SubscribeCommand):
        updates = await self.session.subscribe(
            cmd.mailbox, selected=self._selected)
        return ResponseOk(cmd.tag, cmd.command + b' completed.'), updates

    async def do_unsubscribe(self, cmd: UnsubscribeCommand):
        updates = await self.session.unsubscribe(
            cmd.mailbox, selected=self._selected)
        return ResponseOk(cmd.tag, cmd.command + b' completed.'), updates

    async def do_list(self, cmd: ListCommand):
        mailboxes, updates = await self.session.list_mailboxes(
            cmd.ref_name, cmd.filter, subscribed=cmd.only_subscribed,
            selected=self._selected)
        resp = ResponseOk(cmd.tag, cmd.command + b' completed.')
        resp_type = LSubResponse if cmd.only_subscribed else ListResponse
        for name, sep, attrs in mailboxes:
            resp.add_untagged(resp_type(name, sep, attrs))
        return resp, updates

    async def do_check(self, cmd: CheckCommand):
        updates = await self.session.check_mailbox(
            self.selected, housekeeping=True)
        return ResponseOk(cmd.tag, cmd.command + b' completed.'), updates

    async def do_close(self, cmd: CloseCommand):
        await self.session.expunge_mailbox(self.selected)
        self._selected = None
        return ResponseOk(cmd.tag, cmd.command + b' completed.'), None

    async def do_expunge(self, cmd: ExpungeCommand):
        updates = await self.session.expunge_mailbox(
            self.selected, cmd.uid_set)
        resp = ResponseOk(cmd.tag, cmd.command + b' completed.')
        return resp, updates

    async def do_copy(self, cmd: CopyCommand):
        copy_uid, updates = await self.session.copy_messages(
            self.selected, cmd.sequence_set, cmd.mailbox)
        resp = ResponseOk(cmd.tag, cmd.command + b' completed.', copy_uid)
        return resp, updates

    async def do_fetch(self, cmd: FetchCommand):
        if not cmd.uid:
            self.selected.hide_expunged = True
        messages, updates = await self.session.fetch_messages(
            self.selected, cmd.sequence_set, frozenset(cmd.attributes))
        resp = ResponseOk(cmd.tag, cmd.command + b' completed.')
        session_flags = self.selected.session_flags
        for msg_seq, msg in messages:
            if msg.expunged:
                resp.code = ResponseCode.of(b'EXPUNGEISSUED')
            fetch_data: Dict[FetchAttribute, MaybeBytes] = OrderedDict()
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
                elif msg.expunged:
                    continue
                elif attr.value == b'ENVELOPE':
                    fetch_data[attr] = msg.get_envelope_structure()
                elif attr.value == b'BODYSTRUCTURE':
                    fetch_data[attr] = msg.get_body_structure().extended
                elif attr.value in (b'BODY', b'BODY.PEEK'):
                    if not attr.section:
                        fetch_data[attr] = msg.get_body_structure()
                    elif not attr.section.specifier:
                        fetch_data[attr] = LiteralString(msg.get_body(
                            attr.section.parts))
                    elif attr.section.specifier == b'TEXT':
                        fetch_data[attr] = LiteralString(msg.get_text(
                            attr.section.parts))
                    elif attr.section.specifier in (b'HEADER', b'MIME'):
                        fetch_data[attr] = LiteralString(msg.get_headers(
                            attr.section.parts))
                    elif attr.section.specifier == b'HEADER.FIELDS':
                        fetch_data[attr] = LiteralString(msg.get_headers(
                            attr.section.parts, attr.section.headers))
                    elif attr.section.specifier == b'HEADER.FIELDS.NOT':
                        fetch_data[attr] = LiteralString(msg.get_headers(
                            attr.section.parts, attr.section.headers, True))
                elif attr.value == b'RFC822':
                    fetch_data[attr] = LiteralString(msg.get_body())
                elif attr.value == b'RFC822.HEADER':
                    fetch_data[attr] = LiteralString(msg.get_headers())
                elif attr.value == b'RFC822.TEXT':
                    fetch_data[attr] = LiteralString(msg.get_text())
                elif attr.value == b'RFC822.SIZE':
                    fetch_data[attr] = Number(msg.get_size())
                elif attr.value in (b'BINARY', b'BINARY.PEEK'):
                    parts = attr.section.parts if attr.section else None
                    fetch_data[attr] = LiteralString(
                        msg.get_body(parts, True), True)
                elif attr.value == b'BINARY.SIZE':
                    parts = attr.section.parts if attr.section else None
                    fetch_data[attr] = Number(msg.get_size(parts, True))
            resp.add_untagged(FetchResponse(msg_seq, fetch_data))
        return resp, updates

    async def do_search(self, cmd: SearchCommand):
        if not cmd.uid:
            self.selected.hide_expunged = True
        messages, updates = await self.session.search_mailbox(
            self.selected, cmd.keys)
        resp = ResponseOk(cmd.tag, cmd.command + b' completed.')
        msg_ids: List[int] = []
        for msg_seq, msg in messages:
            if msg.expunged:
                resp.code = ResponseCode.of(b'EXPUNGEISSUED')
            if cmd.uid:
                msg_ids.append(msg.uid)
            else:
                msg_ids.append(msg_seq)
        resp.add_untagged(SearchResponse(msg_ids))
        return resp, updates

    async def do_store(self, cmd: StoreCommand):
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
            fetch_data: Dict[FetchAttribute, MaybeBytes] = \
                {FetchAttribute(b'FLAGS'): ListP(flags, sort=True)}
            if cmd.uid:
                fetch_data[FetchAttribute(b'UID')] = Number(msg.uid)
            resp.add_untagged(FetchResponse(msg_seq, fetch_data))
        return resp, updates

    async def do_idle(self, cmd: IdleCommand):
        if b'IDLE' not in self.capability:
            raise CommandNotAllowed(b'IDLE is disabled.')
        return ResponseOk(cmd.tag, cmd.command + b' completed.'), None

    @classmethod
    async def do_logout(cls, cmd: LogoutCommand):
        raise CloseConnection()

    async def receive_updates(self, cmd: IdleCommand, done: Event) \
            -> Iterable[Response]:
        selected = await self.session.check_mailbox(
            self.selected, wait_on=done)
        self._selected, untagged = selected.fork(cmd)
        return untagged

    @classmethod
    def _get_bad_response(cls, cmd: InvalidCommand) -> ResponseBad:
        if not cmd.command_name:
            return ResponseBad(cmd.tag, b'Command not given.')
        elif not cmd.command_type:
            msg = b'%b: Command not implemented.' % cmd.command_name
            return ResponseBad(cmd.tag, msg)
        else:
            msg = b'%b: Invalid arguments.' % cmd.command_name
            return ResponseBad(cmd.tag, msg)

    @classmethod
    def _get_func_name(cls, cmd: Command) -> str:
        cmd_type = type(cmd)
        while cmd_type.delegate:
            cmd_type = cmd_type.delegate
        cmd_str = str(cmd_type.command, 'ascii').lower()
        return 'do_' + cmd_str

    async def do_command(self, cmd: Command):
        if isinstance(cmd, InvalidCommand):
            return self._get_bad_response(cmd)
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
        if selected:
            self._selected, untagged = selected.fork(cmd)
            response.add_untagged(*untagged)
        return response
