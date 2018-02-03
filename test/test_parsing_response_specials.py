
import unittest

from pymap.parsing.specials import *  # NOQA
from pymap.parsing.response.specials import *  # NOQA


class TestFlagsResponse(unittest.TestCase):

    def test_bytes(self):
        resp = FlagsResponse([br'\One', br'\Two'])
        self.assertEqual(b'* FLAGS (\\One \\Two)\r\n', bytes(resp))


class TestExistsResponse(unittest.TestCase):

    def test_bytes(self):
        resp = ExistsResponse(78)
        self.assertEqual(b'* 78 EXISTS\r\n', bytes(resp))


class TestRecentResponse(unittest.TestCase):

    def test_bytes(self):
        resp = RecentResponse(4)
        self.assertEqual(b'* 4 RECENT\r\n', bytes(resp))


class TestExpungeResponse(unittest.TestCase):

    def test_bytes(self):
        resp = ExpungeResponse(41)
        self.assertEqual(b'* 41 EXPUNGE\r\n', bytes(resp))


class TestFetchResponse(unittest.TestCase):

    def test_bytes(self):
        resp = FetchResponse(56, {FetchAttribute(b'KEY1'): b'VAL1'})
        self.assertEqual(b'* 56 FETCH (KEY1 VAL1)\r\n', bytes(resp))


class TestSearchResponse(unittest.TestCase):

    def test_bytes(self):
        resp = SearchResponse([4, 8, 15, 16, 23, 42])
        self.assertEqual(b'* SEARCH 4 8 15 16 23 42\r\n', bytes(resp))


class TestListResponse(unittest.TestCase):

    def test_bytes(self):
        resp1 = ListResponse('inbox', b'.')
        self.assertEqual(b'* LIST () "." INBOX\r\n', bytes(resp1))
        resp2 = ListResponse('Other.Stuff', b'.', True, False, True, True)
        self.assertEqual(b'* LIST (\\Marked \\Noinferior \\Noselect) '
                         b'"." Other.Stuff\r\n', bytes(resp2))


class TestLSubResponse(unittest.TestCase):

    def test_bytes(self):
        resp1 = LSubResponse('inbox', b'.')
        self.assertEqual(b'* LSUB () "." INBOX\r\n', bytes(resp1))
        resp2 = LSubResponse('Other.Stuff', b'.', True, False, True, True)
        self.assertEqual(b'* LSUB (\\Marked \\Noinferior \\Noselect) '
                         b'"." Other.Stuff\r\n', bytes(resp2))
