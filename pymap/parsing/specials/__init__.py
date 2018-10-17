"""Package of special data objects, usually composed of one of more
primitives.

"""

__all__ = ['AString', 'DateTime', 'FetchAttribute', 'Flag', 'SystemFlag',
           'Keyword', 'Mailbox', 'SearchKey', 'SequenceSet',
           'StatusAttribute', 'Tag']

from .astring import AString
from .datetime_ import DateTime
from .fetchattr import FetchAttribute
from .flag import Flag, SystemFlag, Keyword
from .mailbox import Mailbox
from .searchkey import SearchKey
from .sequenceset import SequenceSet
from .statusattr import StatusAttribute
from .tag import Tag
