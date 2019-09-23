
import unittest
from datetime import datetime, timezone

from pymap.parsing import Params
from pymap.parsing.exceptions import NotParseable
from pymap.parsing.command.auth import CreateCommand, AppendCommand, \
    ListCommand, RenameCommand, StatusCommand
from pymap.parsing.specials import StatusAttribute, Flag
from pymap.parsing.state import ParsingState, ParsingInterrupt, \
    ExpectContinuation


class TestCommandMailboxArg(unittest.TestCase):

    def test_parse(self):
        ret, buf = CreateCommand.parse(b' inbox\n  ', Params())
        self.assertEqual('INBOX', ret.mailbox)
        self.assertEqual(b'  ', buf)


class TestAppendCommand(unittest.TestCase):

    _epoch = datetime(1970, 1, 1, 1, 1, tzinfo=timezone.utc)
    _seen = Flag(br'\Seen')

    def test_parse(self):
        state = ParsingState(continuations=[b'test test!\n  '])
        ret, buf = AppendCommand.parse(
                b' inbox (\\Seen) "01-Jan-1970 01:01:00 +0000" {10}\n',
                Params(state))
        self.assertEqual('INBOX', ret.mailbox)
        self.assertEqual(1, len(ret.messages))
        self.assertEqual(b'test test!', ret.messages[0].literal)
        self.assertEqual({self._seen}, ret.messages[0].flag_set)
        self.assertEqual(self._epoch, ret.messages[0].when)
        self.assertEqual(b'  ', buf)

    def test_parse_multi(self):
        state = ParsingState(continuations=[b'test test! {14}\n'])
        with self.assertRaises(ParsingInterrupt) as raised:
            AppendCommand.parse(b' inbox {10}\n', Params(state))
        expected = raised.exception.expected
        self.assertIsInstance(expected, ExpectContinuation)
        self.assertEqual(14, expected.literal_length)
        state = ParsingState(continuations=[b'test test! {14}\n',
                                            b'second message\n  '])
        ret, buf = AppendCommand.parse(b' inbox {10}\n', Params(state))
        self.assertIsInstance(ret, AppendCommand)
        self.assertEqual('INBOX', ret.mailbox)
        self.assertEqual(2, len(ret.messages))
        self.assertEqual(b'test test!', ret.messages[0].literal)
        self.assertEqual(b'second message', ret.messages[1].literal)
        self.assertEqual(b'  ', buf)

    def test_parse_toobig(self):
        with self.assertRaises(NotParseable) as raised:
            AppendCommand.parse(
                b' inbox {10}\n',
                Params(max_append_len=9, command_name=b'APPEND'))
        self.assertEqual(b'[TOOBIG]', bytes(raised.exception.code))


class TestListCommand(unittest.TestCase):

    def test_parse(self):
        ret, buf = ListCommand.parse(b' one two*\n  ', Params())
        self.assertEqual('one', ret.ref_name)
        self.assertEqual('two*', ret.filter)
        self.assertEqual(b'  ', buf)

    def test_parse_filter_string(self):
        ret, buf = ListCommand.parse(b' one "two*"\n  ', Params())
        self.assertEqual('one', ret.ref_name)
        self.assertEqual('two*', ret.filter)
        self.assertEqual(b'  ', buf)


class TestRenameCommand(unittest.TestCase):

    def test_parse(self):
        ret, buf = RenameCommand.parse(b' one two\n  ', Params())
        self.assertEqual('one', ret.from_mailbox)
        self.assertEqual('two', ret.to_mailbox)
        self.assertEqual(b'  ', buf)


class TestStatusCommand(unittest.TestCase):

    def test_parse(self):
        ret, buf = StatusCommand.parse(b' mbx (MESSAGES UNSEEN)\n  ', Params())
        self.assertEqual('mbx', ret.mailbox)
        self.assertEqual(2, len(ret.status_list))
        self.assertIsInstance(ret.status_list[0], StatusAttribute)
        self.assertEqual(b'MESSAGES', ret.status_list[0].value)
        self.assertIsInstance(ret.status_list[1], StatusAttribute)
        self.assertEqual(b'UNSEEN', ret.status_list[1].value)
        self.assertEqual(b'  ', buf)

    def test_parse_error(self):
        with self.assertRaises(NotParseable):
            StatusCommand.parse(b' mbx ()\n', Params())
