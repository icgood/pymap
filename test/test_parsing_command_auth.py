
import unittest
from datetime import datetime, timezone

from pymap.flags import Flag
from pymap.parsing import NotParseable
from pymap.parsing.specials import StatusAttribute
from pymap.parsing.command import *  # NOQA
from pymap.parsing.command.auth import *  # NOQA


class TestCommandMailboxArg(unittest.TestCase):

    def test_parse(self):
        ret, buf = CreateCommand._parse(b'tag', b' inbox\n  ')
        self.assertEqual('INBOX', ret.mailbox)
        self.assertEqual(b'  ', buf)


class TestAppendCommand(unittest.TestCase):

    def test_parse(self):
        ret, buf = AppendCommand._parse(
            b'tag',
            b' inbox (\\Seen) "01-Jan-1970 01:01:00 +0000" {10}\n',
            continuations=[b'test test!\n  '])
        self.assertEqual(b'tag', ret.tag)
        self.assertEqual('INBOX', ret.mailbox)
        self.assertEqual(b'test test!', ret.message)
        self.assertEqual({Flag(br'\Seen')}, ret.flag_set)
        self.assertEqual(datetime(1970, 1, 1, 1, 1, tzinfo=timezone.utc),
                         ret.when)
        self.assertEqual(b'  ', buf)

    def test_parse_simple(self):
        ret, buf = AppendCommand._parse(b'tag', b' inbox {10}\n',
                                        continuations=[b'test test!\n  '])
        self.assertEqual(b'tag', ret.tag)
        self.assertEqual('INBOX', ret.mailbox)
        self.assertEqual(b'test test!', ret.message)
        self.assertFalse(ret.flag_set)
        self.assertEqual(b'  ', buf)


class TestListCommand(unittest.TestCase):

    def test_parse(self):
        ret, buf = ListCommand._parse(b'tag', b' one two*\n  ')
        self.assertEqual(b'tag', ret.tag)
        self.assertEqual('one', ret.ref_name)
        self.assertEqual('two*', ret.filter)
        self.assertEqual(b'  ', buf)

    def test_parse_filter_string(self):
        ret, buf = ListCommand._parse(b'tag', b' one "two*"\n  ')
        self.assertEqual(b'tag', ret.tag)
        self.assertEqual('one', ret.ref_name)
        self.assertEqual('two*', ret.filter)
        self.assertEqual(b'  ', buf)


class TestRenameCommand(unittest.TestCase):

    def test_parse(self):
        ret, buf = RenameCommand._parse(b'tag', b' one two\n  ')
        self.assertEqual(b'tag', ret.tag)
        self.assertEqual('one', ret.from_mailbox)
        self.assertEqual('two', ret.to_mailbox)
        self.assertEqual(b'  ', buf)


class TestStatusCommand(unittest.TestCase):

    def test_parse(self):
        ret, buf = StatusCommand._parse(b'tag', b' mbx (MESSAGES UNSEEN)\n  ')
        self.assertEqual(b'tag', ret.tag)
        self.assertEqual('mbx', ret.mailbox)
        self.assertEqual(2, len(ret.status_list))
        self.assertIsInstance(ret.status_list[0], StatusAttribute)
        self.assertEqual(b'MESSAGES', ret.status_list[0].value)
        self.assertIsInstance(ret.status_list[1], StatusAttribute)
        self.assertEqual(b'UNSEEN', ret.status_list[1].value)
        self.assertEqual(b'  ', buf)

    def test_parse_error(self):
        with self.assertRaises(NotParseable):
            StatusCommand._parse(b'tag', b' mbx ()\n')
