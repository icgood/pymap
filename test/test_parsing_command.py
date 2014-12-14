
import unittest

from pymap.parsing import NotParseable
from pymap.parsing.command import *


class TestCommand(unittest.TestCase):

    def test_try_parse(self):
        ret, end = Tag.try_parse(b' a[001]  ')
        self.assertIsInstance(ret, Tag)
        self.assertEqual(b'a[001]', ret.value)
        self.assertEqual(9, end)

    def test_try_parse_failure(self):
        with self.assertRaises(NotParseable):
            Tag.try_parse(b'a001')
        with self.assertRaises(NotParseable):
            Tag.try_parse(b'a+b ')

    def test_bytes(self):
        tag1 = Tag(b'a[001]')
        self.assertEqual(b'a[001]', bytes(tag1))
        tag2 = Tag()
        self.assertEqual(b'*', bytes(tag2))
        tag3 = Tag(Tag.CONTINUATION)
        self.assertEqual(b'+', bytes(tag3))
