
import unittest

from pymap.flags import FlagOp, PermanentFlags, SessionFlags
from pymap.message import BaseMessage
from pymap.parsing.command.select import SearchCommand, UidSearchCommand
from pymap.parsing.response import ResponseOk
from pymap.parsing.specials import SequenceSet
from pymap.parsing.specials.flag import Seen, Flagged
from pymap.selected import SelectedMailbox


class TestSelectedMailbox(unittest.TestCase):

    def setUp(self) -> None:
        self.response = ResponseOk(b'.', b'testing')

    @classmethod
    def new_selected(cls) -> SelectedMailbox:
        return SelectedMailbox('test', False,
                               PermanentFlags([Seen, Flagged]),
                               SessionFlags([]))

    @classmethod
    def add_message(cls, selected: SelectedMailbox, uid, flags) -> None:
        selected.add_messages([BaseMessage(uid, flags)])

    @property
    def command(self) -> SearchCommand:
        return SearchCommand(b'.', [], None)

    @property
    def uid_command(self) -> SearchCommand:
        return UidSearchCommand(b'.', [], None)

    def test_add_untagged_recent_equal(self) -> None:
        selected = self.new_selected()
        selected.session_flags.add_recent(1)
        selected.session_flags.add_recent(2)
        self.add_message(selected, 1, [])
        self.add_message(selected, 2, [])
        forked, _ = selected.fork(self.command)
        self.add_message(forked, 1, [])
        self.add_message(forked, 2, [])
        _, untagged = forked.fork(self.command)
        self.response.add_untagged(*untagged)
        self.assertEqual(b'. OK testing\r\n', bytes(self.response))

    def test_add_untagged_recent_increase(self) -> None:
        selected = self.new_selected()
        selected.session_flags.add_recent(1)
        selected.session_flags.add_recent(2)
        self.add_message(selected, 1, [])
        self.add_message(selected, 2, [])
        self.add_message(selected, 3, [])
        forked, _ = selected.fork(self.command)
        forked.session_flags.add_recent(3)
        self.add_message(forked, 1, [])
        self.add_message(forked, 2, [])
        self.add_message(forked, 3, [])
        _, untagged = forked.fork(self.command)
        self.response.add_untagged(*untagged)
        self.assertEqual(b'* 3 RECENT\r\n'
                         b'* 3 FETCH (FLAGS (\\Recent))\r\n'
                         b'. OK testing\r\n', bytes(self.response))

    def test_add_untagged_recent_expunge(self) -> None:
        selected = self.new_selected()
        selected.session_flags.add_recent(1)
        selected.session_flags.add_recent(2)
        self.add_message(selected, 1, [])
        self.add_message(selected, 2, [])
        self.add_message(selected, 3, [])
        forked, _ = selected.fork(self.command)
        self.add_message(forked, 1, [])
        _, untagged = forked.fork(self.command)
        self.response.add_untagged(*untagged)
        self.assertEqual(b'* 3 EXPUNGE\r\n'
                         b'* 2 EXPUNGE\r\n'
                         b'* 1 RECENT\r\n'
                         b'. OK testing\r\n', bytes(self.response))

    def test_add_untagged_equal(self) -> None:
        selected = self.new_selected()
        self.add_message(selected, 1, [])
        self.add_message(selected, 2, [])
        forked, _ = selected.fork(self.command)
        self.add_message(forked, 1, [])
        self.add_message(forked, 2, [])
        _, untagged = forked.fork(self.command)
        self.response.add_untagged(*untagged)
        self.assertEqual(b'. OK testing\r\n', bytes(self.response))

    def test_add_untagged_fetch(self) -> None:
        selected = self.new_selected()
        self.add_message(selected, 1, [])
        self.add_message(selected, 2, [])
        forked, _ = selected.fork(self.command)
        self.add_message(forked, 1, [])
        self.add_message(forked, 2, [Seen])
        self.add_message(forked, 3, [Seen, Flagged])
        self.add_message(forked, 4, [])
        _, untagged = forked.fork(self.command)
        self.response.add_untagged(*untagged)
        self.assertEqual(b'* 4 EXISTS\r\n'
                         b'* 2 FETCH (FLAGS (\\Seen))\r\n'
                         b'* 3 FETCH (FLAGS (\\Flagged \\Seen))\r\n'
                         b'* 4 FETCH (FLAGS ())\r\n'
                         b'. OK testing\r\n', bytes(self.response))

    def test_add_untagged_fetch_uid(self) -> None:
        selected = self.new_selected()
        self.add_message(selected, 1, [])
        self.add_message(selected, 2, [])
        forked, _ = selected.fork(self.uid_command)
        self.add_message(forked, 1, [])
        self.add_message(forked, 2, [Seen])
        self.add_message(forked, 3, [Seen, Flagged])
        self.add_message(forked, 4, [])
        _, untagged = forked.fork(self.uid_command)
        self.response.add_untagged(*untagged)
        self.assertEqual(b'* 4 EXISTS\r\n'
                         b'* 2 FETCH (FLAGS (\\Seen) UID 2)\r\n'
                         b'* 3 FETCH (FLAGS (\\Flagged \\Seen) UID 3)\r\n'
                         b'* 4 FETCH (FLAGS () UID 4)\r\n'
                         b'. OK testing\r\n', bytes(self.response))

    def test_add_untagged_fetch_silenced(self) -> None:
        selected = self.new_selected()
        self.add_message(selected, 1, [])
        self.add_message(selected, 2, [])
        self.add_message(selected, 3, [Seen, Flagged])
        self.add_message(selected, 4, [Seen, Flagged])
        self.add_message(selected, 5, [Flagged])
        self.add_message(selected, 6, [Seen])
        forked, _ = selected.fork(self.uid_command)
        forked.silence(SequenceSet.build([1, 2], True),
                       frozenset([Seen]), FlagOp.ADD)
        forked.silence(SequenceSet.build([3, 4], True),
                       frozenset([Seen]), FlagOp.DELETE)
        forked.silence(SequenceSet.build([5, 6], True),
                       frozenset([Seen]), FlagOp.REPLACE)
        self.add_message(forked, 1, [Seen, Flagged])
        self.add_message(forked, 2, [Seen])
        self.add_message(forked, 3, [])
        self.add_message(forked, 4, [Flagged])
        self.add_message(forked, 5, [Seen, Flagged])
        self.add_message(forked, 6, [Seen])
        _, untagged = forked.fork(self.uid_command)
        self.response.add_untagged(*untagged)
        self.assertEqual(b'* 1 FETCH (FLAGS (\\Flagged \\Seen) UID 1)\r\n'
                         b'* 3 FETCH (FLAGS () UID 3)\r\n'
                         b'* 5 FETCH (FLAGS (\\Flagged \\Seen) UID 5)\r\n'
                         b'. OK testing\r\n', bytes(self.response))

    def test_add_untagged_expunge_hidden(self) -> None:
        selected = self.new_selected()
        self.add_message(selected, 1, [])
        self.add_message(selected, 2, [])
        self.add_message(selected, 3, [])
        self.add_message(selected, 4, [])
        forked, _ = selected.fork(self.command)
        self.add_message(forked, 1, [])
        self.add_message(forked, 4, [])
        self.add_message(forked, 5, [])
        forked.hide_expunged()
        _, untagged = forked.fork(self.command)
        self.response.add_untagged(*untagged)
        self.assertEqual(b'* 5 EXISTS\r\n'
                         b'* 5 FETCH (FLAGS ())\r\n'
                         b'. OK testing\r\n', bytes(self.response))

    def test_add_untagged_expunge(self) -> None:
        selected = self.new_selected()
        self.add_message(selected, 1, [])
        self.add_message(selected, 2, [])
        self.add_message(selected, 3, [])
        self.add_message(selected, 4, [])
        forked, _ = selected.fork(self.command)
        self.add_message(forked, 1, [])
        self.add_message(forked, 4, [])
        _, untagged = forked.fork(self.command)
        self.response.add_untagged(*untagged)
        self.assertEqual(b'* 3 EXPUNGE\r\n'
                         b'* 2 EXPUNGE\r\n'
                         b'. OK testing\r\n', bytes(self.response))

    def test_add_untagged_all(self) -> None:
        selected = self.new_selected()
        self.add_message(selected, 1, [Flagged])
        self.add_message(selected, 2, [])
        self.add_message(selected, 3, [])
        forked, _ = selected.fork(self.uid_command)
        selected.session_flags.add_recent(6)
        self.add_message(forked, 1, [Seen, Flagged])
        self.add_message(forked, 4, [Seen])
        self.add_message(forked, 5, [Seen])
        self.add_message(forked, 6, [Flagged])
        self.add_message(forked, 7, [Seen])
        _, untagged = forked.fork(self.uid_command)
        self.response.add_untagged(*untagged)
        self.assertEqual(b'* 3 EXPUNGE\r\n'
                         b'* 2 EXPUNGE\r\n'
                         b'* 5 EXISTS\r\n'
                         b'* 1 RECENT\r\n'
                         b'* 1 FETCH (FLAGS (\\Flagged \\Seen) UID 1)\r\n'
                         b'* 2 FETCH (FLAGS (\\Seen) UID 4)\r\n'
                         b'* 3 FETCH (FLAGS (\\Seen) UID 5)\r\n'
                         b'* 4 FETCH (FLAGS (\\Flagged \\Recent) UID 6)\r\n'
                         b'* 5 FETCH (FLAGS (\\Seen) UID 7)\r\n'
                         b'. OK testing\r\n', bytes(self.response))

    def test_add_untagged_deleted_bye(self) -> None:
        selected = self.new_selected()
        self.add_message(selected, 1, [])
        forked, _ = selected.fork(self.command)
        self.add_message(forked, 2, [])
        forked.set_deleted()
        _, untagged = forked.fork(self.command)
        self.response.add_untagged(*untagged)
        self.assertEqual(b'* BYE Selected mailbox deleted.\r\n'
                         b'. OK testing\r\n', bytes(self.response))

    def test_add_untagged_uid_validity_bye(self) -> None:
        selected = self.new_selected()
        self.add_message(selected, 1, [])
        forked, _ = selected.fork(self.command)
        self.add_message(forked, 2, [])
        forked.uid_validity = 456
        _, untagged = forked.fork(self.command)
        self.response.add_untagged(*untagged)
        self.assertEqual(b'* BYE [UIDVALIDITY 456] UID validity changed.\r\n'
                         b'. OK testing\r\n', bytes(self.response))
