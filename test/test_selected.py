
import unittest

from pymap.parsing.command.select import SearchCommand, UidSearchCommand
from pymap.parsing.response import ResponseOk
from pymap.parsing.specials.flag import Seen, Flagged
from pymap.selected import SelectedMailbox


class TestSelectedMailbox(unittest.TestCase):

    @property
    def command(self) -> SearchCommand:
        return SearchCommand(b'.', [], None)

    @property
    def uid_command(self) -> SearchCommand:
        return UidSearchCommand(b'.', [], None)

    @property
    def response(self) -> ResponseOk:
        return ResponseOk(b'.', b'testing')

    def test_add_untagged_recent_equal(self):
        selected = SelectedMailbox('test', False)
        selected.session_flags.add_recent(1)
        selected.session_flags.add_recent(2)
        forked = selected.fork()
        response = forked.add_untagged(self.command, self.response)
        self.assertEqual(b'. OK testing\r\n', bytes(response))

    def test_add_untagged_recent(self):
        selected = SelectedMailbox('test', False)
        selected.session_flags.add_recent(1)
        selected.session_flags.add_recent(2)
        forked = selected.fork()
        forked.session_flags.add_recent(3)
        response = forked.add_untagged(self.command, self.response)
        self.assertEqual(b'* 3 RECENT\r\n'
                         b'. OK testing\r\n', bytes(response))

    def test_add_untagged_equal(self):
        selected = SelectedMailbox('test', False)
        selected.add_messages((1, frozenset()),
                              (2, frozenset()))
        forked = selected.fork()
        forked.add_messages((1, frozenset()),
                            (2, frozenset()))
        response = forked.add_untagged(self.command, self.response)
        self.assertEqual(b'. OK testing\r\n', bytes(response))

    def test_add_untagged_fetch(self):
        selected = SelectedMailbox('test', False)
        selected.add_messages((1, frozenset()),
                              (2, frozenset()))
        forked = selected.fork()
        forked.add_messages((1, frozenset()),
                            (2, frozenset([Seen])),
                            (3, frozenset([Seen, Flagged])),
                            (4, frozenset()))
        response = forked.add_untagged(self.command, self.response)
        self.assertEqual(b'* 4 EXISTS\r\n'
                         b'* 2 FETCH (FLAGS (\\Seen))\r\n'
                         b'* 3 FETCH (FLAGS (\\Flagged \\Seen))\r\n'
                         b'* 4 FETCH (FLAGS ())\r\n'
                         b'. OK testing\r\n', bytes(response))

    def test_add_untagged_fetch_uid(self):
        selected = SelectedMailbox('test', False)
        selected.add_messages((1, frozenset()),
                              (2, frozenset()))
        forked = selected.fork()
        forked.add_messages((1, frozenset()),
                            (2, frozenset([Seen])),
                            (3, frozenset([Seen, Flagged])),
                            (4, frozenset()))
        response = forked.add_untagged(self.uid_command, self.response)
        self.assertEqual(b'* 4 EXISTS\r\n'
                         b'* 2 FETCH (FLAGS (\\Seen) UID 2)\r\n'
                         b'* 3 FETCH (FLAGS (\\Flagged \\Seen) UID 3)\r\n'
                         b'* 4 FETCH (FLAGS () UID 4)\r\n'
                         b'. OK testing\r\n', bytes(response))

    def test_add_untagged_fetch_hidden(self):
        selected = SelectedMailbox('test', False)
        selected.add_messages((1, frozenset()),
                              (2, frozenset()))
        forked = selected.fork()
        forked.add_messages((1, frozenset()),
                            (2, frozenset([Seen])),
                            (3, frozenset([Seen, Flagged])),
                            (4, frozenset()))
        forked.hide_fetch(2)
        response = forked.add_untagged(self.uid_command, self.response)
        self.assertEqual(b'* 4 EXISTS\r\n'
                         b'* 3 FETCH (FLAGS (\\Flagged \\Seen) UID 3)\r\n'
                         b'* 4 FETCH (FLAGS () UID 4)\r\n'
                         b'. OK testing\r\n', bytes(response))

    def test_add_untagged_expunge(self):
        selected = SelectedMailbox('test', False)
        selected.add_messages((1, frozenset()),
                              (2, frozenset()),
                              (3, frozenset()),
                              (4, frozenset()))
        forked = selected.fork()
        forked.add_messages((1, frozenset()),
                            (4, frozenset()))
        response = forked.add_untagged(self.uid_command, self.response)
        self.assertEqual(b'* 3 EXPUNGE\r\n'
                         b'* 2 EXPUNGE\r\n'
                         b'. OK testing\r\n', bytes(response))

    def test_add_untagged_all(self):
        selected = SelectedMailbox('test', False)
        selected.add_messages((1, frozenset([Flagged])),
                              (2, frozenset()),
                              (3, frozenset()))
        forked = selected.fork()
        selected.session_flags.add_recent(6)
        forked.add_messages((1, frozenset([Seen, Flagged])),
                            (4, frozenset([Seen])),
                            (5, frozenset([Seen])),
                            (6, frozenset([Flagged])),
                            (7, frozenset([Seen])))
        response = forked.add_untagged(self.uid_command, self.response)
        self.assertEqual(b'* 3 EXPUNGE\r\n'
                         b'* 2 EXPUNGE\r\n'
                         b'* 5 EXISTS\r\n'
                         b'* 1 RECENT\r\n'
                         b'* 1 FETCH (FLAGS (\\Flagged \\Seen) UID 1)\r\n'
                         b'* 2 FETCH (FLAGS (\\Seen) UID 4)\r\n'
                         b'* 3 FETCH (FLAGS (\\Seen) UID 5)\r\n'
                         b'* 4 FETCH (FLAGS (\\Flagged \\Recent) UID 6)\r\n'
                         b'* 5 FETCH (FLAGS (\\Seen) UID 7)\r\n'
                         b'. OK testing\r\n', bytes(response))

    def test_add_untagged_deleted_bye(self):
        selected = SelectedMailbox('test', False)
        selected.add_messages((1, frozenset()))
        forked = selected.fork()
        forked.add_messages((2, frozenset()))
        forked.set_deleted()
        response = forked.add_untagged(self.command, self.response)
        self.assertEqual(b'* BYE Selected mailbox deleted.\r\n'
                         b'. OK testing\r\n', bytes(response))

    def test_add_untagged_uid_validity_bye(self):
        selected = SelectedMailbox('test', False)
        selected.add_messages((1, frozenset()))
        forked = selected.fork()
        forked.add_messages((2, frozenset()))
        forked.set_uid_validity(456)
        response = forked.add_untagged(self.command, self.response)
        self.assertEqual(b'* BYE [UIDVALIDITY 456] UID validity changed.\r\n'
                         b'. OK testing\r\n', bytes(response))
