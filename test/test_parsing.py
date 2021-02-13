
import unittest

from pymap.parsing import Params, ExpectedParseable, Space, EndLine
from pymap.parsing.exceptions import NotParseable
from pymap.parsing.primitives import Nil, Number, Atom, String, QuotedString, \
    List


class TestExpectedParseable(unittest.TestCase):

    def test_parse(self):
        nil, _ = ExpectedParseable.parse(b'nil', Params(expected=[Nil]))
        self.assertIsInstance(nil, Nil)
        num, _ = ExpectedParseable.parse(b'123', Params(expected=[Number]))
        self.assertIsInstance(num, Number)
        atom, _ = ExpectedParseable.parse(b'ATOM', Params(expected=[Atom]))
        self.assertIsInstance(atom, Atom)
        qstr, _ = ExpectedParseable.parse(b'"test"', Params(expected=[String]))
        self.assertIsInstance(qstr, QuotedString)
        list_, _ = ExpectedParseable.parse(b'()', Params(expected=[List]))
        self.assertIsInstance(list_, List)

    def test_parse_expectation_failure(self):
        with self.assertRaises(NotParseable):
            ExpectedParseable.parse(b'ATOM', Params(expected=[Number, Nil]))

    def test_parse_expectation_casting(self):
        num, _ = ExpectedParseable.parse(b'123', Params(expected=[Atom]))
        self.assertIsInstance(num, Atom)
        nil, _ = ExpectedParseable.parse(b'nil', Params(expected=[Atom]))
        self.assertIsInstance(num, Atom)


class TestSpace(unittest.TestCase):

    def test_parse(self):
        ret, buf = Space.parse(b'    ', Params())
        self.assertIsInstance(ret, Space)
        self.assertEqual(4, ret.length)

    def test_parse_failure(self):
        with self.assertRaises(NotParseable):
            Space.parse(b'test ', Params())
        with self.assertRaises(NotParseable):
            Space.parse(b'', Params())

    def test_bytes(self):
        ret = Space(4)
        self.assertEqual(b'    ', bytes(ret))


class TestEndLine(unittest.TestCase):

    def test_parse(self):
        ret, buf = EndLine.parse(b'  \r\n', Params())
        self.assertIsInstance(ret, EndLine)
        self.assertEqual(2, ret.preceding_spaces)
        self.assertTrue(ret.carriage_return)

    def test_parse_no_cr(self):
        ret, buf = EndLine.parse(b'  \n', Params())
        self.assertIsInstance(ret, EndLine)
        self.assertEqual(2, ret.preceding_spaces)
        self.assertFalse(ret.carriage_return)

    def test_parse_failure(self):
        with self.assertRaises(NotParseable):
            EndLine.parse(b'  \r', Params())
        with self.assertRaises(NotParseable):
            EndLine.parse(b' test \r\n', Params())

    def test_bytes(self):
        endl1 = EndLine(4, True)
        self.assertEqual(b'    \r\n', bytes(endl1))
        endl2 = EndLine(0, False)
        self.assertEqual(b'\n', bytes(endl2))
