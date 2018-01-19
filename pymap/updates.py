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

from typing import AbstractSet, Iterable, Union, Optional, Set, FrozenSet

from pymap.parsing.primitives import List, Number
from pymap.parsing.response.specials import ExpungeResponse, FetchResponse, \
    ExistsResponse, RecentResponse
from pymap.parsing.specials import FetchAttribute

__all__ = ['MailboxUpdates']


class MailboxUpdates:

    _FLAGS_ATTR = FetchAttribute(b'FLAGS')
    _UID_ATTR = FetchAttribute(b'UID')

    def __init__(self, exists: int = 0, recent: FrozenSet[int] = None):
        super().__init__()
        self.exists = exists  # type: int
        self.recent = recent or frozenset()  # type: FrozenSet[int]
        self.updates = {}

    def add_expunge(self, *seqs: int):
        for seq in seqs:
            self.updates[seq] = ('expunge', None, None)

    def add_recent(self, *uids: int):
        self.recent = self.recent | frozenset(uids)

    def add_fetch(self, seq: int, flags: AbstractSet[bytes], uid: int):
        self.updates[seq] = ('fetch', frozenset(flags), uid)

    def process(self, updates: Optional['MailboxUpdates'],
                with_uid: bool = False) \
            -> Iterable[Union[ExpungeResponse, FetchResponse]]:
        before_exists = self.exists
        before_recent = len(self.recent)
        if updates:
            self.exists = updates.exists
            self.recent = self.recent | updates.recent
            self.updates.update(updates.updates)
            updates.recent = frozenset()
            updates.updates = {}
        if self.exists != before_exists:
            yield ExistsResponse(updates.exists)
        if len(self.recent) != before_recent:
            yield RecentResponse(len(self.recent))
        for seq in sorted(self.updates.keys()):
            update_type, flags, uid = self.updates[seq]
            if update_type == 'expunge':
                yield ExpungeResponse(seq)
            elif update_type == 'fetch':
                if uid in self.recent:
                    flags = flags | {br'\Recent'}
                data = {self._FLAGS_ATTR: List(flags)}
                if with_uid:
                    data[self._UID_ATTR] = Number(uid)
                yield FetchResponse(seq, data)
        self.updates = {}
