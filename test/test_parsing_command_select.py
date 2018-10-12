
import unittest

from pymap.flag import Flag, FlagOp
from pymap.parsing import NotParseable, Params
from pymap.parsing.command.select import CopyCommand, FetchCommand, \
    StoreCommand, UidCommand, SearchCommand
from pymap.parsing.specials import FetchAttribute, SearchKey


class TestCopyCommand(unittest.TestCase):

    def test_parse(self):
        ret, buf = CopyCommand.parse(b' 1,2,3 mbx\n  ', Params())
        self.assertEqual([1, 2, 3], ret.sequence_set.value)
        self.assertEqual('mbx', ret.mailbox)
        self.assertEqual(b'  ', buf)


class TestFetchCommand(unittest.TestCase):

    def test_parse(self):
        ret, buf = FetchCommand.parse(b' 1,2,3 ENVELOPE\n  ', Params())
        self.assertEqual([1, 2, 3], ret.sequence_set.value)
        self.assertEqual(1, len(ret.attributes))
        self.assertListEqual([FetchAttribute(b'ENVELOPE')], ret.attributes)
        self.assertEqual(b'  ', buf)

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
        self.assertEqual([1, 2, 3], ret.sequence_set.value)
        self.assertSetEqual({Flag(br'\Seen')}, ret.flag_set)
        self.assertEqual(FlagOp.ADD, ret.mode)
        self.assertTrue(ret.silent)
        self.assertEqual(b'  ', buf)

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


class TestUidCommand(unittest.TestCase):

    def test_parse_command_copy(self):
        ret, buf = UidCommand.parse(b' COPY * mbx\n  ', Params())
        self.assertIsInstance(ret, CopyCommand)
        self.assertTrue(ret.sequence_set.uid)
        self.assertTrue(ret.uid)
        self.assertEqual(b'  ', buf)

    def test_parse_command_fetch(self):
        ret, buf = UidCommand.parse(b' FETCH * ENVELOPE\n  ', Params())
        self.assertIsInstance(ret, FetchCommand)
        self.assertTrue(ret.sequence_set.uid)
        self.assertTrue(ret.uid)
        self.assertEqual(b'  ', buf)

    def test_parse_command_store(self):
        ret, buf = UidCommand.parse(b' STORE * FLAGS \\Seen\n  ', Params())
        self.assertIsInstance(ret, StoreCommand)
        self.assertTrue(ret.sequence_set.uid)
        self.assertTrue(ret.uid)
        self.assertEqual(b'  ', buf)

    def test_parse_command_search(self):
        ret, buf = UidCommand.parse(b' SEARCH ALL\n  ', Params())
        self.assertIsInstance(ret, SearchCommand)
        self.assertTrue(ret.uid)
        self.assertEqual(b'  ', buf)

    def test_parse_error(self):
        with self.assertRaises(NotParseable):
            UidCommand.parse(b' NOOP\n', Params())


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
        self.assertEqual('US-ASCII', ret)
        self.assertEqual(b'  ', buf)

    def test_parse(self):
        ret, buf = SearchCommand.parse(b' ALL\n  ', Params())
        self.assertSetEqual({SearchKey(b'ALL')}, ret.keys)
        self.assertEqual('US-ASCII', ret.charset)
        self.assertEqual(b'  ', buf)

    def test_parse_error(self):
        with self.assertRaises(NotParseable):
            SearchCommand.parse(b' TEST\n', Params())
