# Copyright (c) 2014 Ian C. Good
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

from .. import Parseable, NotParseable

__all__ = ['Special', 'InvalidContent']


class InvalidContent(NotParseable, ValueError):
    """Indicates the type of the parsed content was correct, but something
    about the content did not fit what was expected by the special type.

    """
    pass


class Special(Parseable):
    """Base class for special data objects in an IMAP stream.

    """
    pass


from .astring import __all__ as astring_all
from .astring import *  # NOQA
__all__.extend(astring_all)

from .tag import __all__ as tag_all
from .tag import *  # NOQA
__all__.extend(tag_all)

from .datetime import __all__ as datetime_all
from .datetime import *  # NOQA
__all__.extend(datetime_all)

from .flag import __all__ as flag_all
from .flag import *  # NOQA
__all__.extend(flag_all)

from .mailbox import __all__ as mailbox_all
from .mailbox import *  # NOQA
__all__.extend(mailbox_all)

from .statusattr import __all__ as statusattr_all
from .statusattr import *  # NOQA
__all__.extend(statusattr_all)

from .sequenceset import __all__ as sequenceset_all
from .sequenceset import *  # NOQA
__all__.extend(sequenceset_all)

from .fetchattr import __all__ as fetchattr_all
from .fetchattr import *  # NOQA
__all__.extend(fetchattr_all)

from .searchkey import __all__ as searchkey_all
from .searchkey import *  # NOQA
__all__.extend(searchkey_all)
