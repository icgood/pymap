
import unittest

from pymap.flags import FlagOp
from pymap.parsing import Params
from pymap.parsing.exceptions import NotParseable
from pymap.parsing.command.select import ExpungeCommand, CopyCommand, \
    MoveCommand, FetchCommand, StoreCommand, SearchCommand, \
    UidExpungeCommand, UidCopyCommand, UidMoveCommand, UidFetchCommand, \
    UidStoreCommand, UidSearchCommand, IdleCommand
from pymap.parsing.specials import FetchAttribute, SearchKey, Flag


class TestExpungeCommand(unittest.TestCase):

    def test_parse(self):
        ret, buf = ExpungeCommand.parse(b' \n  ', Params())
        self.assertFalse(ret.uid)
        self.assertEqual(b'  ', buf)

    def test_parse_uid(self):
        ret, buf = UidExpungeCommand.parse(b' 12,13,14 \n  ', Params())
        self.assertTrue(ret.uid)
        self.assertTrue(ret.uid_set.uid)
        self.assertEqual([12, 13, 14], ret.uid_set.value)
        self.assertEqual(b'  ', buf)


class TestCopyCommand(unittest.TestCase):

    def test_parse(self):
        ret, buf = CopyCommand.parse(b' 1,2,3 mbx\n  ', Params())
        self.assertFalse(ret.uid)
        self.assertFalse(ret.sequence_set.uid)
        self.assertEqual([1, 2, 3], ret.sequence_set.value)
        self.assertEqual('mbx', ret.mailbox)
        self.assertEqual(b'  ', buf)

    def test_parse_uid(self):
        ret, buf = UidCopyCommand.parse(b' 1,2,3 mbx\n  ', Params())
        self.assertTrue(ret.uid)
        self.assertTrue(ret.sequence_set.uid)


class TestMoveCommand(unittest.TestCase):

    def test_parse(self):
        ret, buf = MoveCommand.parse(b' 1,2,3 mbx\n  ', Params())
        self.assertFalse(ret.uid)
        self.assertFalse(ret.sequence_set.uid)
        self.assertEqual([1, 2, 3], ret.sequence_set.value)
        self.assertEqual('mbx', ret.mailbox)
        self.assertEqual(b'  ', buf)

    def test_parse_uid(self):
        ret, buf = UidMoveCommand.parse(b' 1,2,3 mbx\n  ', Params())
        self.assertTrue(ret.uid)
        self.assertTrue(ret.sequence_set.uid)


class TestFetchCommand(unittest.TestCase):

    def test_parse(self):
        ret, buf = FetchCommand.parse(b' 1,2,3 ENVELOPE\n  ', Params())
        self.assertFalse(ret.uid)
        self.assertFalse(ret.sequence_set.uid)
        self.assertEqual([1, 2, 3], ret.sequence_set.value)
        self.assertEqual(1, len(ret.attributes))
        self.assertListEqual([FetchAttribute(b'ENVELOPE')], ret.attributes)
        self.assertEqual(b'  ', buf)

    def test_parse_uid(self):
        ret, buf = UidFetchCommand.parse(b' 1,2,3 ENVELOPE\n  ', Params())
        self.assertTrue(ret.uid)
        self.assertTrue(ret.sequence_set.uid)

    def test_parse_list(self):
        ret, buf = FetchCommand.parse(b' 1,2,3 (FLAGS ENVELOPE)\n  ', Params())
        self.assertEqual([1, 2, 3], ret.sequence_set.value)
        self.assertListEqual([FetchAttribute(b'FLAGS'),
                              FetchAttribute(b'ENVELOPE')], ret.attributes)
        self.assertEqual(b'  ', buf)

    def test_parse_macro_all(self):
        ret, buf = FetchCommand.parse(b' 1,2,3 ALL\n  ', Params())
        self.assertEqual([1, 2, 3], ret.sequence_set.value)
        self.assertListEqual([FetchAttribute(b'FLAGS'),
                              FetchAttribute(b'INTERNALDATE'),
                              FetchAttribute(b'RFC822.SIZE'),
                              FetchAttribute(b'ENVELOPE')], ret.attributes)
        self.assertEqual(b'  ', buf)

    def test_parse_macro_full(self):
        ret, buf = FetchCommand.parse(b' 1,2,3 FULL\n  ', Params())
        self.assertEqual([1, 2, 3], ret.sequence_set.value)
        self.assertListEqual([FetchAttribute(b'FLAGS'),
                              FetchAttribute(b'INTERNALDATE'),
                              FetchAttribute(b'RFC822.SIZE'),
                              FetchAttribute(b'ENVELOPE'),
                              FetchAttribute(b'BODY')], ret.attributes)
        self.assertEqual(b'  ', buf)

    def test_parse_macro_fast(self):
        ret, buf = FetchCommand.parse(b' 1,2,3 FAST\n  ', Params())
        self.assertEqual([1, 2, 3], ret.sequence_set.value)
        self.assertListEqual([FetchAttribute(b'FLAGS'),
                              FetchAttribute(b'INTERNALDATE'),
                              FetchAttribute(b'RFC822.SIZE')], ret.attributes)
        self.assertEqual(b'  ', buf)


class TestStoreCommand(unittest.TestCase):

    def test_parse(self):
        ret, buf = StoreCommand.parse(
            b' 1,2,3 +FLAGS.SILENT (\\Seen)\n  ', Params())
        self.assertFalse(ret.uid)
        self.assertFalse(ret.sequence_set.uid)
        self.assertEqual([1, 2, 3], ret.sequence_set.value)
        self.assertSetEqual({Flag(br'\Seen')}, ret.flag_set)
        self.assertEqual(FlagOp.ADD, ret.mode)
        self.assertTrue(ret.silent)
        self.assertEqual(b'  ', buf)

    def test_parse_uid(self):
        ret, buf = UidStoreCommand.parse(
            b' 1,2,3 +FLAGS.SILENT (\\Seen)\n  ', Params())
        self.assertTrue(ret.uid)
        self.assertTrue(ret.sequence_set.uid)

    def test_parse_simple(self):
        ret, buf = StoreCommand.parse(b' 1,2,3 FLAGS \\Seen\n  ', Params())
        self.assertEqual([1, 2, 3], ret.sequence_set.value)
        self.assertSetEqual({Flag(br'\Seen')}, ret.flag_set)
        self.assertEqual(FlagOp.REPLACE, ret.mode)
        self.assertFalse(ret.silent)
        self.assertEqual(b'  ', buf)

    def test_parse_error(self):
        with self.assertRaises(NotParseable):
            StoreCommand.parse(b' 1,2,3 TEST (\\Seen)\n', Params())


class TestSearchCommand(unittest.TestCase):

    def test_parse_charset(self):
        ret, buf = SearchCommand._parse_charset(
            b' CHARSET "utf-8"  ', Params())
        self.assertEqual('utf-8', ret)
        self.assertEqual(b'  ', buf)

    def test_parse_charset_error(self):
        with self.assertRaises(NotParseable):
            SearchCommand._parse_charset(b' CHARSET "test"', Params())

    def test_parse_charset_default(self):
        ret, buf = SearchCommand._parse_charset(b'  ', Params())
        self.assertIsNone(ret)
        self.assertEqual(b'  ', buf)

    def test_parse(self):
        ret, buf = SearchCommand.parse(b' ALL\n  ', Params())
        self.assertFalse(ret.uid)
        self.assertSetEqual({SearchKey(b'ALL')}, ret.keys)
        self.assertIsNone(ret.charset)
        self.assertEqual(b'  ', buf)

    def test_parse_uid(self):
        ret, buf = UidSearchCommand.parse(b' ALL\n  ', Params())
        self.assertTrue(ret.uid)

    def test_parse_error(self):
        with self.assertRaises(NotParseable):
            SearchCommand.parse(b' TEST\n', Params())


class TestIdleCommand(unittest.TestCase):

    def test_parse(self):
        ret, buf = IdleCommand.parse(b' \r\nabc', Params())
        self.assertIsInstance(ret, IdleCommand)
        self.assertEqual(b'DONE', ret.continuation)
        self.assertEqual(b'abc', buf)

    def test_parse_error(self):
        with self.assertRaises(NotParseable):
            IdleCommand.parse(b' STUFF\r\n', Params())

    def test_parse_done(self):
        ok, buf = IdleCommand(b'tag').parse_done(b'DONE\r\nabc')
        self.assertTrue(ok)
        self.assertEqual(b'abc', buf)

    def test_parse_done_bad(self):
        ok, buf = IdleCommand(b'tag').parse_done(b' DONE\r\n')
        self.assertFalse(ok)
        self.assertEqual(b'', buf)
        ok, buf = IdleCommand(b'tag').parse_done(b'TEST\r\n')
        self.assertFalse(ok)
        self.assertEqual(b'', buf)
