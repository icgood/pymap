# Copyright (c) 2018 Ian C. Good
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

import os.path
import random
from collections import defaultdict
from contextlib import closing
from typing import List, Dict, Set
from weakref import WeakSet

from pkg_resources import resource_listdir, resource_stream

from pymap.mailbox import MailboxSession
from pymap.message import BaseMessage
from .message import Message

__all__ = ['State']


class _Mailbox:
    sep = b'.'

    def __init__(self):
        self.next_uid: int = 100
        self.uid_validity: int = random.randint(1, 32768)
        self.messages: List[BaseMessage] = []
        self.recent: Set[int] = set()
        self.sessions: Set[MailboxSession] = WeakSet()
        self.subscribed = False

    def claim_uid(self):
        uid = self.next_uid
        self.next_uid += 1
        return uid


class State:
    mailboxes: Dict[str, _Mailbox] = defaultdict(lambda: _Mailbox())

    @classmethod
    def init(cls):
        cls.mailboxes.clear()
        resource = 'pymap.demo'
        for mailbox_name in resource_listdir(resource, 'data'):
            mailbox_path = os.path.join('data', mailbox_name)
            mailbox = cls.mailboxes[mailbox_name]
            message_names = sorted(resource_listdir(resource, mailbox_path))
            for message_name in message_names:
                message_path = os.path.join(mailbox_path, message_name)
                message_stream = resource_stream(resource, message_path)
                message_uid = mailbox.claim_uid()
                with closing(message_stream):
                    flags_line = message_stream.readline()
                    message_flags = frozenset(flags_line.split())
                    message_data = message_stream.read()
                if br'\Recent' in message_flags:
                    message_flags = message_flags - {br'\Recent'}
                    mailbox.recent.add(message_uid)
                message = Message.parse(message_uid, message_data,
                                        message_flags)
                mailbox.messages.append(message)
        cls.mailboxes['Trash'] = _Mailbox()
