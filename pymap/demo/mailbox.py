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

import asyncio
import random

from pymap.interfaces import MailboxInterface
from pymap.exceptions import *  # NOQA
from .message import Message

__all__ = ['Mailbox']


class Mailbox(MailboxInterface):

    sep = b'.'
    flags = [br'\Seen', br'\Recent', br'\Answered', br'\Deleted', br'\Draft',
             br'\Flagged']
    permanent_flags = flags

    def __init__(self, name):
        super().__init__(name)
        self.uid_validity = random.randint(1, 32768)
        self.messages = []

    @property
    def exists(self):
        return len(self.messages)

    @property
    def recent(self):
        recent = 0
        for msg in self.messages:
            if br'\Recent' in msg.flags:
                recent += 1
        return recent

    @property
    def unseen(self):
        unseen = 0
        for msg in self.messages:
            if br'\Seen' not in msg.flags:
                unseen += 1
        return unseen

    @property
    def first_unseen(self):
        for msg in self.messages:
            if br'\Seen' not in msg.flags:
                return msg.seq

    @property
    def next_uid(self):
        max_uid = 0
        for msg in self.messages:
            if msg.uid > max_uid:
                max_uid = msg.uid
        return max_uid + 1

    @asyncio.coroutine
    def get_messages_by_seq(self, seq_set):
        max_seq = self.exists
        return [msg for msg in self.messages
                if seq_set.contains(msg.seq, max_seq)]

    @asyncio.coroutine
    def get_messages_by_uid(self, uid_set):
        max_uid = self.next_uid - 1
        return [msg for msg in self.messages
                if uid_set.contains(msg.uid, max_uid)]

    @asyncio.coroutine
    def append_message(self, message, flag_list=None, when=None):
        msg = Message(self.exists, self.next_uid, flag_list, message)
        self.messages.append(msg)

    @asyncio.coroutine
    def expunge(self):
        new_messages = []
        for msg in self.messages:
            if br'\Deleted' not in msg.flags:
                new_messages.append(msg)
        self.messages = new_messages

    @asyncio.coroutine
    def copy(self, messages, mailbox):
        raise NotImplementedError

    @asyncio.coroutine
    def search(self, keys):
        raise NotImplementedError

    @asyncio.coroutine
    def update_flags(self, messages, flag_list, mode='replace'):
        for msg in messages:
            if mode == 'add':
                msg.flags = list(set(msg.flags) | set(flag_list))
            elif mode == 'delete':
                msg.flags = list(set(msg.flags) - set(flag_list))
            else:
                msg.flags = flag_list

    @asyncio.coroutine
    def get_unseen(self):
        count = 0
        for msg in self.messages:
            if br'\Seen' not in msg.flags:
                count += 1
        return count

    @asyncio.coroutine
    def poll(self):
        pass
