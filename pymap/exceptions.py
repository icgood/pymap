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

"""Module containing the exceptions that may be used by pymap plugins..

"""

from .core import PymapError

__all__ = ['MailboxNotFound', 'MailboxConflict', 'MailboxHasChildren',
           'MailboxReadOnly', 'AppendFailure']


class MailboxError(PymapError):

    def __init__(self, mailbox):
        super().__init__(mailbox)
        self.mailbox = mailbox


class MailboxNotFound(MailboxError):
    """The requested mailbox was not found."""
    pass


class MailboxConflict(MailboxError):
    """The mailbox cannot be created or renamed because of a naming conflict
    with another mailbox.

    """
    pass


class MailboxHasChildren(MailboxError):
    """The mailbox cannot be deleted because there are other inferior
    heirarchical mailboxes below it.

    """
    pass


class MailboxReadOnly(MailboxError):
    """The mailbox is opened read-only and the requested operation is not
    allowed.

    """
    pass


class AppendFailure(MailboxError):
    """The mailbox append operation failed."""
    pass
