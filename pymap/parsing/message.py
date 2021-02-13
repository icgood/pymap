
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from ..parsing.specials import Flag, ExtensionOptions

__all__ = ['AppendMessage']


@dataclass(frozen=True)
class AppendMessage:
    """A single message from the APPEND command.

    Args:
        literal: The message literal.
        when: The internal timestamp to assign to the message.
        flag_set: The flags to assign to the message.
        options: The extension options in use for the message.

    """

    literal: bytes
    when: Optional[datetime] = None
    flag_set: frozenset[Flag] = field(default_factory=frozenset)
    options: ExtensionOptions = field(default_factory=ExtensionOptions.empty)
