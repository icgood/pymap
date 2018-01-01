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

from pymap.exceptions import *  # NOQA
from pymap.interfaces import SessionInterface
from .mailbox import Mailbox

__all__ = ['Session']


class Session(SessionInterface):

    def __init__(self, user):
        super().__init__(user)
        self.mailboxes = [Mailbox(name) for name in Mailbox.messages.keys()]

    @classmethod
    @asyncio.coroutine
    def login(cls, result):
        if result.authcid == 'demouser' and result.check_secret('demopass'):
            return cls(result.authcid)

    @asyncio.coroutine
    def list_mailboxes(self, subscribed=False):
        return self.mailboxes

    @asyncio.coroutine
    def get_mailbox(self, name):
        for mbx in self.mailboxes:
            if mbx.name == name:
                return mbx
        raise MailboxNotFound(name)

    @asyncio.coroutine
    def create_mailbox(self, name):
        for mbx in self.mailboxes:
            if mbx.name == name:
                raise MailboxConflict(name)
        self.mailboxes.append(Mailbox(name))

    @asyncio.coroutine
    def delete_mailbox(self, name):
        for i, mbx in enumerate(self.mailboxes):
            if mbx.name == name:
                self.mailboxes.pop(i)
                break
        else:
            raise MailboxNotFound(name)

    @asyncio.coroutine
    def rename_mailbox(self, before_name, after_name):
        for mbx in self.mailboxes:
            if mbx.name == after_name:
                raise MailboxConflict(after_name)
        for mbx in self.mailboxes:
            if mbx.name == before_name:
                mbx.name = after_name
                break
        else:
            raise MailboxNotFound(before_name)

    @asyncio.coroutine
    def subscribe(self, name):
        pass

    @asyncio.coroutine
    def unsubscribe(self, name):
        pass
