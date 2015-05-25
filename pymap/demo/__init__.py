# Copyright (c) 2015 Ian C. Good
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#

import re
import os.path
from heapq import heappush
from contextlib import closing

from pkg_resources import resource_listdir, resource_stream

from .mailbox import Mailbox
from .message import Message
from .session import Session

__all__ = ['add_subparser', 'init']


def _load_data():
    for mailbox_name in resource_listdir('pymap.demo', 'data'):
        mailbox_path = os.path.join('data', mailbox_name)
        messages = []
        for message_name in resource_listdir('pymap.demo', mailbox_path):
            match = re.match(r'^message-(\d+)\.txt$', message_name)
            if not match:
                continue
            message_uid = int(match.group(1))
            message_path = os.path.join(mailbox_path, message_name)
            message_stream = resource_stream('pymap.demo', message_path)
            with closing(message_stream):
                flags_line = message_stream.readline()
                message_flags = frozenset(flags_line.split())
                message_data = message_stream.read()
            heappush(messages, (message_uid, message_flags, message_data))
        mailbox_data = [Message(uid, flags, data)
                        for uid, flags, data in messages]
        Mailbox.messages[mailbox_name] = mailbox_data


def add_subparser(subparsers):
    subparsers.add_parser('demo')


def init(args):
    _load_data()
    return Session.login
