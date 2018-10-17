import os.path
import random
from collections import defaultdict
from contextlib import closing
from datetime import datetime
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
                    timestamp = float(message_stream.readline())
                    message_flags = frozenset(flags_line.split())
                    message_dt = datetime.utcfromtimestamp(timestamp)
                    message_data = message_stream.read()
                if br'\Recent' in message_flags:
                    message_flags = message_flags - {br'\Recent'}
                    mailbox.recent.add(message_uid)
                message = Message.parse(message_uid, message_data,
                                        message_flags,
                                        internal_date=message_dt)
                mailbox.messages.append(message)
        cls.mailboxes['Trash'] = _Mailbox()
