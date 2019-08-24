
import unittest
from datetime import datetime

from pymap.flags import FlagOp, PermanentFlags, SessionFlags
from pymap.message import BaseMessage
from pymap.parsing.command.select import SearchCommand, UidSearchCommand
from pymap.parsing.response import ResponseOk
from pymap.parsing.specials import SequenceSet, ObjectId
from pymap.parsing.specials.flag import Seen, Flagged, Flag
from pymap.selected import SelectedMailbox

_Keyword = Flag(b'$Keyword')


class _Message(BaseMessage):

    async def load_content(self, requirement):
        raise RuntimeError()


class TestSelectedMailbox(unittest.TestCase):

    def setUp(self) -> None:
        self.response = ResponseOk(b'.', b'testing')

    @classmethod
    def new_selected(cls, guid: bytes = b'test') -> SelectedMailbox:
        return SelectedMailbox(ObjectId(guid), False,
                               PermanentFlags([Seen, Flagged]),
                               SessionFlags([_Keyword]))

    @classmethod
    def set_messages(cls, selected: SelectedMailbox,
                     expunged, messages) -> None:
        updates = [_Message(uid, datetime.now(), flags)
                   for uid, flags in messages]
        selected.add_updates(updates, expunged)

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
        self.set_messages(selected, [],
                          [(1, []), (2, [])])
        forked, _ = selected.fork(self.command)
        self.set_messages(forked, [],
                          [(1, []), (2, [])])
        _, untagged = forked.fork(self.command)
        self.response.add_untagged(*untagged)
        self.assertEqual(b'. OK testing\r\n', bytes(self.response))

    def test_add_untagged_recent_increase(self) -> None:
        selected = self.new_selected()
        selected.session_flags.add_recent(1)
        selected.session_flags.add_recent(2)
        self.set_messages(selected, [],
                          [(1, []), (2, []), (3, [])])
        forked, _ = selected.fork(self.command)
        forked.session_flags.add_recent(3)
        self.set_messages(forked, [], [])
        _, untagged = forked.fork(self.command)
        self.response.add_untagged(*untagged)
        self.assertEqual(b'* 3 RECENT\r\n'
                         b'* 3 FETCH (FLAGS (\\Recent))\r\n'
                         b'. OK testing\r\n', bytes(self.response))

    def test_add_untagged_session_flag_add(self) -> None:
        selected = self.new_selected()
        self.set_messages(selected, [],
                          [(1, []), (2, [Seen]), (3, [])])
        forked, _ = selected.fork(self.command)
        forked.session_flags.update(2, [_Keyword], FlagOp.ADD)
        self.set_messages(forked, [], [])
        _, untagged = forked.fork(self.command)
        self.response.add_untagged(*untagged)
        self.assertEqual(b'* 2 FETCH (FLAGS (\\Seen $Keyword))\r\n'
                         b'. OK testing\r\n', bytes(self.response))

    def test_add_untagged_recent_expunge(self) -> None:
        selected = self.new_selected()
        selected.session_flags.add_recent(1)
        selected.session_flags.add_recent(2)
        self.set_messages(selected, [],
                          [(1, []), (2, []), (3, [])])
        forked, _ = selected.fork(self.command)
        self.set_messages(forked, [2, 3],
                          [(1, [])])
        _, untagged = forked.fork(self.command)
        self.response.add_untagged(*untagged)
        self.assertEqual(b'* 3 EXPUNGE\r\n'
                         b'* 2 EXPUNGE\r\n'
                         b'* 1 RECENT\r\n'
                         b'. OK testing\r\n', bytes(self.response))

    def test_add_untagged_equal(self) -> None:
        selected = self.new_selected()
        self.set_messages(selected, [],
                          [(1, []), (2, [])])
        forked, _ = selected.fork(self.command)
        self.set_messages(forked, [],
                          [(1, []), (2, [])])
        _, untagged = forked.fork(self.command)
        self.response.add_untagged(*untagged)
        self.assertEqual(b'. OK testing\r\n', bytes(self.response))

    def test_add_untagged_fetch(self) -> None:
        selected = self.new_selected()
        self.set_messages(selected, [],
                          [(1, []), (2, [])])
        forked, _ = selected.fork(self.command)
        self.set_messages(forked, [],
                          [(2, [Seen]), (3, [Seen, Flagged]), (4, [])])
        _, untagged = forked.fork(self.command)
        self.response.add_untagged(*untagged)
        self.assertEqual(b'* 4 EXISTS\r\n'
                         b'* 2 FETCH (FLAGS (\\Seen))\r\n'
                         b'* 3 FETCH (FLAGS (\\Flagged \\Seen))\r\n'
                         b'* 4 FETCH (FLAGS ())\r\n'
                         b'. OK testing\r\n', bytes(self.response))

    def test_add_untagged_fetch_uid(self) -> None:
        selected = self.new_selected()
        self.set_messages(selected, [],
                          [(1, []), (2, [])])
        forked, _ = selected.fork(self.uid_command)
        self.set_messages(forked, [],
                          [(2, [Seen]), (3, [Seen, Flagged]), (4, [])])
        _, untagged = forked.fork(self.uid_command)
        self.response.add_untagged(*untagged)
        self.assertEqual(b'* 4 EXISTS\r\n'
                         b'* 2 FETCH (FLAGS (\\Seen) UID 2)\r\n'
                         b'* 3 FETCH (FLAGS (\\Flagged \\Seen) UID 3)\r\n'
                         b'* 4 FETCH (FLAGS () UID 4)\r\n'
                         b'. OK testing\r\n', bytes(self.response))

    def test_add_untagged_fetch_silenced(self) -> None:
        selected = self.new_selected()
        self.set_messages(selected, [],
                          [(1, []), (2, []), (3, [Seen, Flagged]),
                           (4, [Seen, Flagged]), (5, [Flagged]), (6, [Seen])])
        forked, _ = selected.fork(self.uid_command)
        forked.silence(SequenceSet.build([1, 2]),
                       frozenset([Seen]), FlagOp.ADD)
        forked.silence(SequenceSet.build([3, 4]),
                       frozenset([Seen]), FlagOp.DELETE)
        forked.silence(SequenceSet.build([5, 6]),
                       frozenset([Seen]), FlagOp.REPLACE)
        self.set_messages(forked, [],
                          [(1, [Seen, Flagged]), (2, [Seen]), (3, []),
                           (4, [Flagged]), (5, [Seen, Flagged]), (6, [Seen])])
        _, untagged = forked.fork(self.uid_command)
        self.response.add_untagged(*untagged)
        self.assertEqual(b'* 1 FETCH (FLAGS (\\Flagged \\Seen) UID 1)\r\n'
                         b'* 3 FETCH (FLAGS () UID 3)\r\n'
                         b'* 5 FETCH (FLAGS (\\Flagged \\Seen) UID 5)\r\n'
                         b'. OK testing\r\n', bytes(self.response))

    def test_add_untagged_expunge_hidden(self) -> None:
        selected = self.new_selected()
        self.set_messages(selected, [],
                          [(1, []), (2, []), (3, []), (4, [])])
        forked, _ = selected.fork(self.command)
        forked.hide_expunged = True
        self.set_messages(forked, [2, 3],
                          [(5, [Flagged])])
        _, untagged = forked.fork(self.command)
        self.response.add_untagged(*untagged)
        self.assertEqual(b'* 5 EXISTS\r\n'
                         b'* 5 FETCH (FLAGS (\\Flagged))\r\n'
                         b'. OK testing\r\n', bytes(self.response))

    def test_add_untagged_expunge(self) -> None:
        selected = self.new_selected()
        self.set_messages(selected, [],
                          [(1, []), (2, []), (3, []), (4, [])])
        forked, _ = selected.fork(self.command)
        self.set_messages(forked, [2, 3],
                          [(5, [])])
        _, untagged = forked.fork(self.command)
        self.response.add_untagged(*untagged)
        self.assertEqual(b'* 3 EXPUNGE\r\n'
                         b'* 2 EXPUNGE\r\n'
                         b'* 3 EXISTS\r\n'
                         b'* 3 FETCH (FLAGS ())\r\n'
                         b'. OK testing\r\n', bytes(self.response))

    def test_add_untagged_all(self) -> None:
        selected = self.new_selected()
        self.set_messages(selected, [],
                          [(1, [Flagged]), (2, []), (3, [])])
        forked, _ = selected.fork(self.uid_command)
        selected.session_flags.add_recent(6)
        self.set_messages(forked, [2, 3],
                          [(1, [Seen, Flagged]), (4, [Seen]), (5, [Seen]),
                           (6, [Flagged]), (7, [Seen])])
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
        self.set_messages(selected, [],
                          [(1, [])])
        forked, _ = selected.fork(self.command)
        self.set_messages(forked, [1],
                          [(2, [])])
        forked.set_deleted()
        _, untagged = forked.fork(self.command)
        self.response.add_untagged(*untagged)
        self.assertEqual(b'* BYE Selected mailbox no longer exists.\r\n'
                         b'. OK testing\r\n', bytes(self.response))
