
import unittest
from unittest.mock import MagicMock
from datetime import datetime, timezone

from pymap.parsing import Params
from pymap.parsing.exceptions import NotParseable
from pymap.parsing.command.auth import CreateCommand, AppendCommand, \
    ListCommand, RenameCommand, StatusCommand
from pymap.parsing.message import PreparedMessage
from pymap.parsing.specials import StatusAttribute, Flag
from pymap.parsing.state import ParsingState, ParsingInterrupt
from pymap.parsing.state.message import ExpectPreparedMessage

v = memoryview


class TestCommandMailboxArg(unittest.TestCase):

    def test_parse(self):
        ret, buf = CreateCommand.parse(b' inbox\n  ', Params())
        self.assertEqual('INBOX', ret.mailbox)
        self.assertEqual(b'  ', buf)


class TestAppendCommand(unittest.TestCase):

    _epoch = datetime(1970, 1, 1, 1, 1, tzinfo=timezone.utc)
    _seen = Flag(br'\Seen')

    def test_parse(self):
        state = ParsingState(continuations=[v(b'test test!\n  ')])
        with self.assertRaises(ParsingInterrupt) as raised:
            AppendCommand.parse(
                b' inbox (\\Seen) "01-Jan-1970 01:01:00 +0000" {10}\n',
                Params(state))
        expected = raised.exception.expected
        self.assertIsInstance(expected, ExpectPreparedMessage)
        self.assertEqual('INBOX', expected.mailbox)
        self.assertEqual(b'test test!', expected.message.literal)
        self.assertEqual({self._seen}, expected.message.flag_set)
        self.assertEqual(self._epoch, expected.message.when)

    def test_parse_prepared(self):
        prepared1 = MagicMock(PreparedMessage)
        prepared2 = MagicMock(PreparedMessage)
        state = ParsingState(continuations=[v(b'test test! {14}\n'),
                                            v(b'second message\n  ')],
                             prepared_messages=[])
        with self.assertRaises(ParsingInterrupt) as raised:
            AppendCommand.parse(b' inbox {10}\n', Params(state))
        expected = raised.exception.expected
        self.assertIsInstance(expected, ExpectPreparedMessage)
        self.assertEqual('INBOX', expected.mailbox)
        self.assertEqual(b'test test!', expected.message.literal)
        self.assertFalse(expected.message.flag_set)
        state = ParsingState(continuations=[v(b'test test! {14}\n'),
                                            v(b'second message\n  ')],
                             prepared_messages=[prepared1])
        with self.assertRaises(ParsingInterrupt) as raised:
            AppendCommand.parse(b' inbox {10}\n', Params(state))
        expected = raised.exception.expected
        self.assertIsInstance(expected, ExpectPreparedMessage)
        self.assertEqual('INBOX', expected.mailbox)
        self.assertEqual(b'second message', expected.message.literal)
        self.assertFalse(expected.message.flag_set)
        state = ParsingState(continuations=[v(b'test test! {14}\n'),
                                            v(b'second message\n  ')],
                             prepared_messages=[prepared1, prepared2])
        ret, buf = AppendCommand.parse(b' inbox {10}\n', Params(state))
        self.assertIsInstance(ret, AppendCommand)
        self.assertEqual('INBOX', ret.mailbox)
        self.assertEqual([prepared1, prepared2], ret.messages)
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
