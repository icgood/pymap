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

"""Module defining the interfaces available to pymap backends.

"""

import asyncio

__all__ = ['SessionInterface', 'MailboxInterface', 'MessageInterface']


class SessionInterface(object):
    """Corresponds to a single, authenticated IMAP session."""

    def __init__(self, user):
        super().__init__()

        #: The identity of the authenticated user.
        self.user = user

    @asyncio.coroutine
    def list_mailboxes(self, subscribed=False):
        """List the mailboxes owned by the user.

        :param bool subscribed: If true, only list the subscribed mailboxes.
        :returns: list of :class:`Mailbox` objects.

        """
        raise NotImplementedError

    @asyncio.coroutine
    def get_mailbox(self, name):
        """Retrieves a :class:`Mailbox` object corresponding to an existing
        mailbox owned by the user. Raises an exception if the mailbox does not
        yet exist.

        :param str name: The name of the mailbox.
        :rtype: :class:`Mailbox`
        :raises: :class:`~pymap.exceptions.MailboxNotFound`

        """
        raise NotImplementedError

    @asyncio.coroutine
    def create_mailbox(self, name):
        """Creates a new mailbox owned by the user.

        .. seealso: `RFC 3501 6.3.3
        <https://tools.ietf.org/html/rfc3501#section-6.3.3>`_

        :param str name: The name of the mailbox.
        :raises: :class:`~pymap.exceptions.MailboxConflict`

        """
        raise NotImplementedError

    @asyncio.coroutine
    def delete_mailbox(self, name):
        """Deletes the mailbox owned by the user.

        .. seealso: `RFC 3501 6.3.4
        <https://tools.ietf.org/html/rfc3501#section-6.3.4>`_

        :param str name: The name of the mailbox.
        :raises: :class:`~pymap.exceptions.MailboxNotFound`,
                 :class:`~pymap.exceptions.MailboxHasChildren`

        """
        raise NotImplementedError

    @asyncio.coroutine
    def rename_mailbox(self, before_name, after_name):
        """Renames the mailbox owned by the user.

        .. seealso: `RFC 3501 6.3.5
        <https://tools.ietf.org/html/rfc3501#section-6.3.5>`_

        :param str before_name: The name of the mailbox before the rename.
        :param str after_name: The name of the mailbox after the rename.
        :raises: :class:`~pymap.exceptions.MailboxNotFound`,
                 :class:`~pymap.exceptions.MailboxConflict`

        """
        raise NotImplementedError

    @asyncio.coroutine
    def append_message(self, mailbox, message, flag_list=None, when=None):
        """Appends a message to the end of the mailbox.

        .. seealso: `RFC 3501 6.3.11
        <https://tools.ietf.org/html/rfc3501#section-6.3.11>`_

        :param str mailbox: The name of the mailbox.
        :param bytes message: The contents of the message.
        :param flag_list: List of flag bytestrings.
        :param when: The internal time associated with the message.
        :type when: :py:class:`~datetime.datetime`
        :raises: :class:`~pymap.exceptions.MailboxNotFound`,
                 :class:`~pymap.exceptions.AppendFailure`

        """
        raise NotImplementedError

    @asyncio.coroutine
    def subscribe(self, name):
        """Mark the given folder name as subscribed, whether or not the given
        folder name currently exists.

        .. seealso: `RFC 3501 6.3.6
        <https://tools.ietf.org/html/rfc3501#section-6.3.6>`_

        :param str name: The name of the folder.

        """
        raise NotImplementedError

    @asyncio.coroutine
    def unsubscribe(self, name):
        """Remove the given folder name from the subscription list, whether or
        not the given folder name currently exists.

        .. seealso: `RFC 3501 6.3.6
        <https://tools.ietf.org/html/rfc3501#section-6.3.6>`_

        :param str name: The name of the folder.

        """
        raise NotImplementedError


class MailboxInterface(object):
    """Corresponds to a mailbox available to the IMAP session."""

    def __init__(self, name):
        super().__init__()

        #: The name of the mailbox.
        self.name = name

    @asyncio.coroutine
    def get_messages_by_seq(self, seqs):
        """Get a list of :class:`Message` objects corresponding to given
        sequence set.

        :param seqs: List of items, as described in
                     :class:`~pymap.parsing.specials.SequenceSet`.
        :returns: List of :class:`Message` objects.

        """
        raise NotImplementedError

    @asyncio.coroutine
    def get_messages_by_uid(self, uids):
        """Get a list of :class:`Message` objects corresponding to the given
        UIDs.

        :param seqs: List of items, as described in
                     :class:`~pymap.parsing.specials.SequenceSet`.
        :returns: List of :class:`Message` objects.

        """
        raise NotImplementedError

    @asyncio.coroutine
    def expunge(self):
        """All messages that are marked as deleted are immediately expunged
        from the mailbox.

        .. seealso: `RFC 3501 6.4.3
        <https://tools.ietf.org/html/rfc3501#section-6.4.3>`_

        :raises: :class:`~pymap.exceptions.MailboxReadOnly`

        """
        raise NotImplementedError

    @asyncio.coroutine
    def copy(self, messages, mailbox):
        """Copy a set of messages into the given mailbox.

        .. seealso: `RFC 3501 6.4.7
        <https://tools.ietf.org/html/rfc3501#section-6.4.7>`_

        :param messages: List of :class:`Message` objects.
        :param str name: Name of the mailbox to copy messages into.
        :raises: :class:`~pymap.exceptions.MailboxNotFound`

        """
        raise NotImplementedError

    @asyncio.coroutine
    def search(self, keys):
        """Get a list of :class:`Message` objects in the current mailbox that
        meet the given search criteria.

        .. seealso: `RFC 3501 7.2.5
        <https://tools.ietf.org/html/rfc3501#section-7.2.5>`_

        :param list keys: List of :class:`~pymap.parsing.specials.SearchKey`
                          objects specifying the search criteria.

        """
        raise NotImplementedError

    @asyncio.coroutine
    def update_flags(self, messages, flag_list, mode='replace'):
        """Update the flags for the given set of messages.

        .. seealso: `RFC 3501 6.4.6
        <https://tools.ietf.org/html/rfc3501#section-6.4.6>`_

        :param messages: List of :class:`Message` objects.
        :param flag_list: List of flag bytestrings.
        :param str mode: Update mode, can be ``replace``, ``add`` or
                         ``delete``.

        """
        raise NotImplementedError

    @asyncio.coroutine
    def poll(self):
        """Checks the mailbox for any changes. This first time this is called
        on the object, the ``exists`` and ``recent`` keys are always returned.

        :returns: Dictionary with anything that has changed since the last
                  :meth:`.poll`.

        """
        raise NotImplementedError


class MessageInterface(object):
    """Corresponds to a single message, as it exists in a single mailbox."""

    def __init__(self, seq, uid, guid):
        super().__init__()

        #: The message's sequence number in relation to other messages in the
        #: mailbox.
        self.seq = seq

        #: The message's unique identifier in the mailbox.
        self.uid = uid

        #: The message's globally unique identifier across all messages in all
        #: of the user's mailboxes.
        self.guid = guid

    @asyncio.coroutine
    def fetch(self, attributes):
        """Get the requested attributes associated with the message.

        .. seealso: `RFC 3501 7.4.2
        <https://tools.ietf.org/html/rfc3501#section-7.4.2>`_

        :param attributes: List of
                           :class:`~pymap.parsing.specials.FetchAttribute`
                           objects.
        :returns: Dictionary keyed on the requested attributes.

        """
        raise NotImplementedError
