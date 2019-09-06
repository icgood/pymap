"""Append a message directly to a user's mailbox."""

from __future__ import annotations

import sys
import time
import traceback
from argparse import FileType
from typing import Tuple, TextIO

from .command import ClientCommand
from ..grpc.admin_pb2 import AppendRequest, AppendResponse, Login, \
    SUCCESS, ERROR_RESPONSE


class AppendCommand(ClientCommand):

    success = '2.0.0 Message delivered'
    messages = {'InvalidAuth': '5.7.8 Authentication credentials invalid',
                'TimedOut': '4.4.2 Connection timed out',
                'ConnectionFailed': '4.3.0 Connection failed',
                'UnhandledError': '4.3.0 Unhandled system error',
                'MailboxNotFound': '4.2.0 Message not deliverable',
                'AppendFailure': '4.2.0 Message not deliverable'}

    @classmethod
    def add_subparser(cls, name: str, subparsers) -> None:
        subparser = subparsers.add_parser(
            name, description=__doc__,
            help='append a message to a mailbox')
        subparser.add_argument('--from', metavar='ADDRESS', dest='sender',
                               default='', help='the message envelope sender')
        subparser.add_argument('--to', metavar='ADDRESS', dest='recipient',
                               help='the message envelope recipient')
        subparser.add_argument('--mailbox', metavar='NAME',
                               help='the mailbox name')
        subparser.add_argument('--timestamp', type=int, metavar='SECONDS',
                               help='the message timestamp (defualt: now)')
        subparser.add_argument('--data', type=FileType('rb'), metavar='FILE',
                               default=sys.stdin.buffer,
                               help='the message data (default: stdin)')
        subparser.add_argument('user', help='the user name')
        flags = subparser.add_argument_group('message flags')
        flags.add_argument('--flag', dest='flags', action='append',
                           metavar='VAL', help='a message flag or keyword')
        flags.add_argument('--flagged', dest='flags', action='append_const',
                           const='\\Flagged', help='the message is flagged')
        flags.add_argument('--seen', dest='flags', action='append_const',
                           const='\\Seen', help='the message is seen')
        flags.add_argument('--draft', dest='flags', action='append_const',
                           const='\\Draft', help='the message is a draft')
        flags.add_argument('--deleted', dest='flags', action='append_const',
                           const='\\Deleted', help='the message is deleted')
        flags.add_argument('--answered', dest='flags', action='append_const',
                           const='\\Answered', help='the message is answered')

    async def run(self, fileobj: TextIO) -> int:
        args = self.args
        recipient = args.recipient or args.user
        data = args.data.read()
        when: int = args.timestamp or int(time.time())
        login = Login(user=args.user)
        req = AppendRequest(login=login, sender=args.sender,
                            recipient=recipient, mailbox=args.mailbox,
                            data=data, flags=args.flags, when=when)
        try:
            res = await self.stub.Append(req)
        except OSError:
            traceback.print_exc()
            code, msg = 1, self.messages['ConnectionFailed']
        except Exception:
            traceback.print_exc()
            code, msg = 1, self.messages['UnhandledError']
        else:
            print(res, file=sys.stderr)
            code, msg = self._parse(res)
        print(msg, file=fileobj)
        return code

    def _parse(self, response: AppendResponse) -> Tuple[int, str]:
        if response.result == SUCCESS:
            return 0, self.success
        elif response.result == ERROR_RESPONSE:
            try:
                msg = self.messages[response.error_type]
            except KeyError:
                msg = self.messages['UnhandledError']
            return 1, msg
        else:
            raise NotImplementedError(response.result)
