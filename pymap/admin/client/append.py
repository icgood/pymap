"""Append a message directly to a user's mailbox."""

import sys
import time
from argparse import ArgumentParser, FileType, Namespace
from typing import Tuple

from .command import ClientCommand
from ..grpc.admin_grpc import AdminStub
from ..grpc.admin_pb2 import AppendRequest, AppendResponse


class AppendCommand(ClientCommand):

    @classmethod
    def init(cls, parser: ArgumentParser, subparsers) \
            -> Tuple[str, 'AppendCommand']:
        subparser = subparsers.add_parser(
            'append', description=__doc__,
            help='append a message to a mailbox')
        subparser.add_argument('--mailbox', default='INBOX',
                               help='the mailbox name (default: INBOX)')
        subparser.add_argument('--timestamp', type=float, metavar='SECONDS',
                               help='the message timestamp')
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
        return 'append', cls()

    async def run(self, stub: AdminStub, args: Namespace) -> AppendResponse:
        data = args.data.read()
        when: float = args.timestamp or time.time()
        req = AppendRequest(user=args.user, mailbox=args.mailbox,
                            data=data, flags=args.flags, when=when)
        return await stub.Append(req)
