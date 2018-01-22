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
from typing import Iterable

from pymap.flag import SessionFlags
from pymap.parsing.specials import Flag
from pymap.structure import MessageStructure

__all__ = ['Message']


class Message(MessageStructure):

    @classmethod
    def parse(cls, uid: int, data: bytes,
              permanent_flags: Iterable[Flag] = None,
              session_flags: SessionFlags = None,
              internal_date: datetime = None):
        msg = email.message_from_bytes(data, policy=SMTP)
        return cls(uid, msg, permanent_flags, session_flags,
                   internal_date or datetime.now(timezone.utc))

    def __copy__(self) -> 'Message':
        return Message(self.uid, self.message, self.permanent_flags,
                       self.session_flags, self.internal_date)
