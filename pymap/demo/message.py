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

import email
from datetime import datetime, timezone
from email.policy import SMTP
from typing import Optional, Iterable, FrozenSet

from pymap.structure import MessageStructure

__all__ = ['Message']


class Message(MessageStructure):

    def __init__(self, uid: int, flags: Iterable[bytes], data: bytes,
                 when: Optional[datetime] = None):
        super().__init__(uid, email.message_from_bytes(data, policy=SMTP))
        self.flags = frozenset(flags)  # type: FrozenSet[bytes]
        self.internal_date = (
                when or datetime.now(timezone.utc)
        )  # type: datetime
