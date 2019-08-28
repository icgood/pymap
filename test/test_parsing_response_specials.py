
import unittest

from pymap.parsing.response.specials import FlagsResponse, ExistsResponse, \
    RecentResponse, ExpungeResponse, FetchResponse, SearchResponse, \
    ESearchResponse, ListResponse, LSubResponse
from pymap.parsing.specials import FetchAttribute, FetchValue


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
        resp = FetchResponse(56, [
            FetchValue.of(FetchAttribute(b'KEY1'), b'VAL1')])
        self.assertEqual(b'* 56 FETCH (KEY1 VAL1)\r\n', bytes(resp))


class TestSearchResponse(unittest.TestCase):

    def test_bytes(self):
        resp = SearchResponse([4, 8, 15, 16, 23, 42])
        self.assertEqual(b'* SEARCH 4 8 15 16 23 42\r\n', bytes(resp))


class TestESearchResponse(unittest.TestCase):

    def test_bytes(self):
        resp = ESearchResponse(b'tag', True, {b'one': b'2', b'three': b'4'})
        self.assertEqual(b'* (TAG "tag") UID ONE 2 THREE 4\r\n', bytes(resp))


class TestListResponse(unittest.TestCase):

    def test_bytes(self):
        resp1 = ListResponse('inbox', '.', [])
        self.assertEqual(b'* LIST () "." INBOX\r\n', bytes(resp1))
        resp2 = ListResponse('Other.Stuff', '.',
                             [b'Marked', b'Noinferior', b'Noselect'])
        self.assertEqual(b'* LIST (\\Marked \\Noinferior \\Noselect) '
                         b'"." Other.Stuff\r\n', bytes(resp2))


class TestLSubResponse(unittest.TestCase):

    def test_bytes(self):
        resp1 = LSubResponse('inbox', '.', [])
        self.assertEqual(b'* LSUB () "." INBOX\r\n', bytes(resp1))
        resp2 = LSubResponse('Other.Stuff', '.',
                             [b'Marked', b'Noinferior', b'Noselect'])
        self.assertEqual(b'* LSUB (\\Marked \\Noinferior \\Noselect) '
                         b'"." Other.Stuff\r\n', bytes(resp2))
