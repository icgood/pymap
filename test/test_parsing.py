
import unittest

from pymap.parsing import *
from pymap.parsing.primitives import *


class TestParseable(unittest.TestCase):

    def test_parse(self):
        nil, _ = Parseable.parse(b'nil', [Nil])
        self.assertIsInstance(nil, Nil)
        num, _ = Parseable.parse(b'123', [Number])
        self.assertIsInstance(num, Number)
        atom, _ = Parseable.parse(b'ATOM', [Atom])
        self.assertIsInstance(atom, Atom)
        qstr, _ = Parseable.parse(b'"test"', [String])
        self.assertIsInstance(qstr, QuotedString)
        list, _ = Parseable.parse(b'()', [List])
        self.assertIsInstance(list, List)

    def test_parse_expectation_failure(self):
        with self.assertRaises(NotParseable):
            Parseable.parse(b'ATOM', expected=[Number, Nil])

    def test_parse_expectation_casting(self):
        num, _ = Parseable.parse(b'123', [Atom])
        self.assertIsInstance(num, Atom)
        nil, _ = Parseable.parse(b'nil', [Atom])
        self.assertIsInstance(num, Atom)


class TestSpace(unittest.TestCase):

    def test_parse(self):
        ret, buf = Space.parse(b'    ')
        self.assertIsInstance(ret, Space)
        self.assertEqual(4, ret.length)

    def test_parse_failure(self):
        with self.assertRaises(NotParseable):
            Space.parse(b'test ')
        with self.assertRaises(NotParseable):
            Space.parse(b'')

    def test_bytes(self):
        ret = Space(4)
        self.assertEqual(b'    ', bytes(ret))


class TestEndLine(unittest.TestCase):

    def test_parse(self):
        ret, buf = EndLine.parse(b'  \r\n')
        self.assertIsInstance(ret, EndLine)
        self.assertEqual(2, ret.preceding_spaces)
        self.assertTrue(ret.carriage_return)

    def test_parse_no_cr(self):
        ret, buf = EndLine.parse(b'  \n')
        self.assertIsInstance(ret, EndLine)
        self.assertEqual(2, ret.preceding_spaces)
        self.assertFalse(ret.carriage_return)

    def test_parse_failure(self):
        with self.assertRaises(NotParseable):
            EndLine.parse(b'  \r')
        with self.assertRaises(NotParseable):
            EndLine.parse(b' test \r\n')

    def test_bytes(self):
        endl1 = EndLine(4, True)
        self.assertEqual(b'    \r\n', bytes(endl1))
        endl2 = EndLine(0, False)
        self.assertEqual(b'\n', bytes(endl2))
