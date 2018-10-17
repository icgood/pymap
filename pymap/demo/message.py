import email
from datetime import datetime, timezone
from email.message import EmailMessage
from email.policy import SMTP
from typing import cast, Iterable

from pymap.message import BaseLoadedMessage
from pymap.parsing.specials import Flag

__all__ = ['Message']


class Message(BaseLoadedMessage):

    @classmethod
    def parse(cls, uid: int, data: bytes,
              permanent_flags: Iterable[Flag] = None,
              internal_date: datetime = None) -> 'Message':
        msg = email.message_from_bytes(data, policy=SMTP)
        email_msg = cast(EmailMessage, msg)
        return cls(uid, email_msg, permanent_flags,
                   internal_date or datetime.now(timezone.utc))

    def __copy__(self):
        return Message(self.uid, self.contents, self.permanent_flags,
                       self.internal_date)
