
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional, NamedTuple, FrozenSet

from ..parsing.specials import Flag, ExtensionOptions, ObjectId

__all__ = ['AppendMessage', 'PreparedMessage']


class AppendMessage(NamedTuple):
    """A single message from the APPEND command.

    Args:
        literal: The message literal.
        when: The internal timestamp to assign to the message.
        flag_set: The flags to assign to the message.
        options: The extension options in use for the message.

    """

    literal: bytes
    when: Optional[datetime]
    flag_set: FrozenSet[Flag]
    options: Optional[ExtensionOptions] = None


class PreparedMessage(NamedTuple):
    """A message that has been prepared for appending to a mailbox.

    Args:
        when: The internal timestamp to assign to the message.
        flag_set: The flags to assign to the message.
        email_id: An email object ID to assign to the message.
        thread_id: A thread object ID to assign to the message.
        options: The extension options in use for the message.
        ref: A strong reference to an object that will be held until the append
            operation succeeds or fails, for use with :func:`weakref.finalize`.

    """

    when: Optional[datetime]
    flag_set: FrozenSet[Flag]
    email_id: ObjectId
    thread_id: ObjectId
    options: Optional[ExtensionOptions] = None
    ref: Any = None
