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

__all__ = ['Special', 'InvalidContent', 'AString', 'DateTime',
           'FetchAttribute', 'Flag', 'Mailbox', 'SearchKey', 'SequenceSet',
           'StatusAttribute', 'Tag']


class InvalidContent(NotParseable, ValueError):
    """Indicates the type of the parsed content was correct, but something
    about the content did not fit what was expected by the special type.

    """
    pass


class Special(Parseable):
    """Base class for special data objects in an IMAP stream."""

    def __bytes__(self):
        raise NotImplementedError


from .astring import AString  # NOQA
from .datetime import DateTime  # NOQA
from .fetchattr import FetchAttribute  # NOQA
from .flag import Flag  # NOQA
from .mailbox import Mailbox  # NOQA
from .searchkey import SearchKey  # NOQA
from .sequenceset import SequenceSet  # NOQA
from .statusattr import StatusAttribute  # NOQA
from .tag import Tag  # NOQA
