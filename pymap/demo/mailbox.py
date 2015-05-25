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
from copy import copy
from weakref import WeakSet

from pymap.interfaces import MailboxInterface
from pymap.exceptions import *  # NOQA
from .message import Message

__all__ = ['Mailbox']


class Mailbox(MailboxInterface):

    sep = b'.'
    flags = [br'\Seen', br'\Recent', br'\Answered', br'\Deleted', br'\Draft',
             br'\Flagged']
    permanent_flags = flags

    uid_validities = {}
    messages = {}
    instances = WeakSet()

    def __init__(self, name):
        super().__init__(name)
        self.instances.add(self)
        self.uid_validity = self.uid_validities.setdefault(
            name, random.randint(1, 32768))
        self._reset_changes()

    def _reset_changes(self):
        self.changes = {'expunge': [], 'flags': []}

    @property
    def _messages(self):
        return self.messages[self.name]

    @_messages.setter
    def _messages(self, messages):
        self.messages[self.name] = messages

    @property
    def exists(self):
        return len(self._messages)

    @property
    def recent(self):
        recent = 0
        for msg in self._messages:
            if br'\Recent' in msg.flags:
                recent += 1
        return recent

    @property
    def unseen(self):
        unseen = 0
        for msg in self._messages:
            if br'\Seen' not in msg.flags:
                unseen += 1
        return unseen

    @property
    def first_unseen(self):
        for i, msg in enumerate(self._messages):
            if br'\Seen' not in msg.flags:
                return i + 1

    @property
    def next_uid(self):
        max_uid = 0
        for msg in self._messages:
            if msg.uid > max_uid:
                max_uid = msg.uid
        return max_uid + 1

    @asyncio.coroutine
    def get_messages_by_seq(self, seq_set):
        max_seq = self.exists
        return [(i+1, msg) for i, msg in enumerate(self._messages)
                if seq_set.contains(i+1, max_seq)]

    @asyncio.coroutine
    def get_messages_by_uid(self, uid_set):
        max_uid = self.next_uid - 1
        return [(i+1, msg) for i, msg in enumerate(self._messages)
                if uid_set.contains(msg.uid, max_uid)]

    @asyncio.coroutine
    def append_message(self, message, flag_set=None, when=None):
        msg = Message(self.next_uid, flag_set, message)
        self._messages.append(msg)
        for instance in self.instances:
            instance.changes['new_messages'] = True

    @asyncio.coroutine
    def expunge(self):
        new_messages = []
        for i, msg in enumerate(self._messages):
            if br'\Deleted' in msg.flags:
                for instance in self.instances:
                    instance.changes['expunge'].append(i+1)
            else:
                new_messages.append(msg)
        self._messages = new_messages

    @asyncio.coroutine
    def copy(self, messages, mailbox):
        raise NotImplementedError

    @asyncio.coroutine
    def search(self, keys):
        raise NotImplementedError

    @asyncio.coroutine
    def update_flags(self, messages, flag_set, mode='replace', silent=False):
        for msg_seq, msg in messages:
            before_flags = copy(msg.flags)
            if mode == 'add':
                msg.flags = msg.flags | flag_set
            elif mode == 'subtract':
                msg.flags = msg.flags - flag_set
            else:
                msg.flags = flag_set
            if before_flags != msg.flags:
                for instance in self.instances:
                    if instance != self or not silent:
                        instance.changes['flags'].append((msg_seq, msg))

    @asyncio.coroutine
    def poll(self):
        old_changes = self.changes
        self._reset_changes()
        return old_changes
