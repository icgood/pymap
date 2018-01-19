
import unittest

from pymap.flag import Flag
from pymap.parsing import NotParseable
from pymap.parsing.specials import FetchAttribute, SearchKey
from pymap.parsing.command import *  # NOQA
from pymap.parsing.command.select import *  # NOQA


class TestCopyCommand(unittest.TestCase):

    def test_parse(self):
        ret, buf = CopyCommand.parse(b' 1,2,3 mbx\n  ')
        self.assertEqual([1, 2, 3], ret.sequence_set.sequences)
        self.assertEqual('mbx', ret.mailbox)
        self.assertEqual(b'  ', buf)


class TestFetchCommand(unittest.TestCase):

    def test_parse(self):
        ret, buf = FetchCommand.parse(b' 1,2,3 ENVELOPE\n  ')
        self.assertEqual([1, 2, 3], ret.sequence_set.sequences)
        self.assertEqual(1, len(ret.attributes))
        self.assertSetEqual({FetchAttribute(b'ENVELOPE')}, ret.attributes)
        self.assertEqual(b'  ', buf)

    def test_parse_list(self):
        ret, buf = FetchCommand.parse(b' 1,2,3 (FLAGS ENVELOPE)\n  ')
        self.assertEqual([1, 2, 3], ret.sequence_set.sequences)
        self.assertSetEqual({FetchAttribute(b'FLAGS'),
                             FetchAttribute(b'ENVELOPE')}, ret.attributes)
        self.assertEqual(b'  ', buf)

    def test_parse_macro_all(self):
        ret, buf = FetchCommand.parse(b' 1,2,3 ALL\n  ')
        self.assertEqual([1, 2, 3], ret.sequence_set.sequences)
        self.assertSetEqual({FetchAttribute(b'FLAGS'),
                             FetchAttribute(b'INTERNALDATE'),
                             FetchAttribute(b'RFC822.SIZE'),
                             FetchAttribute(b'ENVELOPE')}, ret.attributes)
        self.assertEqual(b'  ', buf)

    def test_parse_macro_full(self):
        ret, buf = FetchCommand.parse(b' 1,2,3 FULL\n  ')
        self.assertEqual([1, 2, 3], ret.sequence_set.sequences)
        self.assertSetEqual({FetchAttribute(b'FLAGS'),
                             FetchAttribute(b'INTERNALDATE'),
                             FetchAttribute(b'RFC822.SIZE'),
                             FetchAttribute(b'ENVELOPE'),
                             FetchAttribute(b'BODY')}, ret.attributes)
        self.assertEqual(b'  ', buf)

    def test_parse_macro_fast(self):
        ret, buf = FetchCommand.parse(b' 1,2,3 FAST\n  ')
        self.assertEqual([1, 2, 3], ret.sequence_set.sequences)
        self.assertSetEqual({FetchAttribute(b'FLAGS'),
                             FetchAttribute(b'INTERNALDATE'),
                             FetchAttribute(b'RFC822.SIZE')}, ret.attributes)
        self.assertEqual(b'  ', buf)


class TestStoreCommand(unittest.TestCase):

    def test_parse(self):
        ret, buf = StoreCommand.parse(b' 1,2,3 +FLAGS.SILENT (\\Seen)\n  ')
        self.assertEqual([1, 2, 3], ret.sequence_set.sequences)
        self.assertSetEqual({Flag(br'\Seen')}, ret.flag_set)
        self.assertEqual('add', ret.mode)
        self.assertTrue(ret.silent)
        self.assertEqual(b'  ', buf)

    def test_parse_simple(self):
        ret, buf = StoreCommand.parse(b' 1,2,3 FLAGS \\Seen\n  ')
        self.assertEqual([1, 2, 3], ret.sequence_set.sequences)
        self.assertSetEqual({Flag(br'\Seen')}, ret.flag_set)
        self.assertEqual('replace', ret.mode)
        self.assertFalse(ret.silent)
        self.assertEqual(b'  ', buf)

    def test_parse_error(self):
        with self.assertRaises(NotParseable):
            StoreCommand.parse(b' 1,2,3 TEST (\\Seen)\n')


class TestUidCommand(unittest.TestCase):

    def test_parse_command_copy(self):
        ret, buf = UidCommand.parse(b' COPY * mbx\n  ')
        self.assertIsInstance(ret, CopyCommand)
        self.assertTrue(ret.sequence_set.uid)
        self.assertEqual(b'  ', buf)

    def test_parse_command_fetch(self):
        ret, buf = UidCommand.parse(b' FETCH * ENVELOPE\n  ')
        self.assertIsInstance(ret, FetchCommand)
        self.assertTrue(ret.sequence_set.uid)
        self.assertEqual(b'  ', buf)

    def test_parse_command_store(self):
        ret, buf = UidCommand.parse(b' STORE * FLAGS \\Seen\n  ')
        self.assertIsInstance(ret, StoreCommand)
        self.assertTrue(ret.sequence_set.uid)
        self.assertEqual(b'  ', buf)

    def test_parse_command_search(self):
        ret, buf = UidCommand.parse(b' SEARCH ALL\n  ')
        self.assertIsInstance(ret, SearchCommand)
        self.assertTrue(ret.uid)
        self.assertEqual(b'  ', buf)

    def test_parse_error(self):
        with self.assertRaises(NotParseable):
            UidCommand.parse(b' NOOP\n')


class TestSearchCommand(unittest.TestCase):

    def test_parse_charset(self):
        ret, buf = SearchCommand._parse_charset(b' CHARSET "utf-8"  ')
        self.assertEqual('utf-8', ret)
        self.assertEqual(b'  ', buf)

    def test_parse_charset_error(self):
        with self.assertRaises(NotParseable):
            SearchCommand._parse_charset(b' CHARSET "test"')

    def test_parse_charset_default(self):
        ret, buf = SearchCommand._parse_charset(b'  ')
        self.assertEqual('US-ASCII', ret)
        self.assertEqual(b'  ', buf)

    def test_parse(self):
        ret, buf = SearchCommand.parse(b' ALL\n  ')
        self.assertSetEqual({SearchKey(b'ALL')}, ret.keys)
        self.assertEqual('US-ASCII', ret.charset)
        self.assertEqual(b'  ', buf)

    def test_parse_error(self):
        with self.assertRaises(NotParseable):
            SearchCommand.parse(b' TEST\n')
