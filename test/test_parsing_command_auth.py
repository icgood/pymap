
import unittest
from datetime import datetime, timezone

from pymap.flag import Flag
from pymap.parsing import NotParseable, Params
from pymap.parsing.command.auth import CreateCommand, AppendCommand, \
    ListCommand, RenameCommand, StatusCommand
from pymap.parsing.specials import StatusAttribute


class TestCommandMailboxArg(unittest.TestCase):

    def test_parse(self):
        ret, buf = CreateCommand.parse(b' inbox\n  ', Params())
        self.assertEqual('INBOX', ret.mailbox)
        self.assertEqual(b'  ', buf)


class TestAppendCommand(unittest.TestCase):

    def test_parse(self):
        ret, buf = AppendCommand.parse(
            b' inbox (\\Seen) "01-Jan-1970 01:01:00 +0000" {10}\n',
            Params(continuations=[b'test test!\n  ']))
        self.assertEqual('INBOX', ret.mailbox)
        self.assertEqual(b'test test!', ret.message)
        self.assertEqual({Flag(br'\Seen')}, ret.flag_set)
        self.assertEqual(datetime(1970, 1, 1, 1, 1, tzinfo=timezone.utc),
                         ret.when)
        self.assertEqual(b'  ', buf)

    def test_parse_simple(self):
        ret, buf = AppendCommand.parse(
            b' inbox {10}\n',
            Params(continuations=[b'test test!\n  ']))
        self.assertEqual('INBOX', ret.mailbox)
        self.assertEqual(b'test test!', ret.message)
        self.assertFalse(ret.flag_set)
        self.assertEqual(b'  ', buf)


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
