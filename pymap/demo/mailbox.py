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

import random
from copy import copy
from weakref import WeakSet

from pymap.interfaces import MailboxInterface
from .message import Message

__all__ = ['Mailbox']


class Mailbox(MailboxInterface):
    sep = b'.'
    flags = [br'\Seen', br'\Recent', br'\Answered', br'\Deleted', br'\Draft',
             br'\Flagged']
    permanent_flags = flags

    next_uids = {}
    uid_validities = {}
    messages = {}
    instances = {}

    def __init__(self, name):
        super().__init__(name)
        self._instances.add(self)
        self.uid_validity = self.uid_validities.setdefault(
            name, random.randint(1, 32768))
        self._reset_changes()
        self._new_messages = False
        self._messages = copy(self.messages[self.name])

    def _reset_changes(self):
        self._changes = {'expunge': set(), 'fetch': {}}

    @property
    def _instances(self):
        return self.instances.setdefault(self.name, WeakSet())

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
        return self.next_uids.setdefault(self.name, self.exists + 1)

    def _increment_next_uid(self):
        next_uid = self.next_uid
        self.next_uids[self.name] += 1
        return next_uid

    async def sync(self):
        if self._new_messages:
            self._messages = copy(self.messages[self.name])
            self._new_messages = False

    async def get_messages_by_seq(self, seq_set):
        max_seq = self.exists
        return [(i + 1, msg) for i, msg in enumerate(self._messages)
                if seq_set.contains(i + 1, max_seq)]

    async def get_messages_by_uid(self, uid_set):
        max_uid = self.next_uid - 1
        return [(i + 1, msg) for i, msg in enumerate(self._messages)
                if uid_set.contains(msg.uid, max_uid)]

    async def append_message(self, message, flag_set=None, when=None):
        msg_uid = self._increment_next_uid()
        msg = Message(msg_uid, flag_set, message, when=when)
        self._messages.append(msg)
        for instance in self._instances:
            instance._changes['append'] = True
            instance._new_messages = True
        self.messages[self.name] = self._messages
        self._new_messages = False

    async def expunge(self):
        new_messages = []
        for i, msg in enumerate(self._messages):
            if br'\Deleted' in msg.flags:
                for instance in self._instances:
                    instance._changes['expunge'].add(i + 1)
                    instance._new_messages = True
            else:
                new_messages.append(msg)
        if self._new_messages:
            self._messages = new_messages
            self.messages[self.name] = new_messages
            self._new_messages = False

    async def copy(self, messages, mailbox):
        raise NotImplementedError

    async def search(self, keys):
        raise NotImplementedError

    async def update_flags(self, messages, flag_set, mode='replace',
                           silent=False):
        for msg_seq, msg in messages:
            before_flags = copy(msg.flags)
            if mode == 'add':
                msg.flags = msg.flags | flag_set
            elif mode == 'subtract':
                msg.flags = msg.flags - flag_set
            else:
                msg.flags = flag_set
            if before_flags != msg.flags:
                for instance in self._instances:
                    if instance != self or not silent:
                        instance._changes['fetch'][msg_seq] = msg.flags

    async def poll(self):
        old_changes = self._changes
        self._reset_changes()
        return old_changes
