
import unittest

from pymap.parsing import Params, NotParseable, Parseable, Space, EndLine
from pymap.parsing.primitives import Nil, Number, Atom, String, QuotedString, \
    ListP


class TestNotParseable(unittest.TestCase):

    def test_bytes(self):
        exc = NotParseable(b'one two three')
        self.assertEqual(0, exc.offset)
        self.assertEqual(b'', exc.before)
        self.assertEqual(b'one two three', exc.after)
        self.assertEqual('[:ERROR:]one two three', str(exc))

    def test_memoryview(self):
        mem = memoryview(b'one two three')[4:]
        exc = NotParseable(mem)
        self.assertEqual(4, exc.offset)
        self.assertEqual(b'one ', exc.before)
        self.assertEqual(b'two three', exc.after)
        self.assertEqual(b'one [:ERROR:]two three', bytes(exc))
        self.assertEqual('one [:ERROR:]two three', str(exc))


class TestParseable(unittest.TestCase):

    def test_parse(self):
        nil, _ = Parseable.parse(b'nil', Params(expected=[Nil]))
        self.assertIsInstance(nil, Nil)
        num, _ = Parseable.parse(b'123', Params(expected=[Number]))
        self.assertIsInstance(num, Number)
        atom, _ = Parseable.parse(b'ATOM', Params(expected=[Atom]))
        self.assertIsInstance(atom, Atom)
        qstr, _ = Parseable.parse(b'"test"', Params(expected=[String]))
        self.assertIsInstance(qstr, QuotedString)
        list_, _ = Parseable.parse(b'()', Params(expected=[ListP]))
        self.assertIsInstance(list_, ListP)

    def test_parse_expectation_failure(self):
        with self.assertRaises(NotParseable):
            Parseable.parse(b'ATOM', Params(expected=[Number, Nil]))

    def test_parse_expectation_casting(self):
        num, _ = Parseable.parse(b'123', Params(expected=[Atom]))
        self.assertIsInstance(num, Atom)
        nil, _ = Parseable.parse(b'nil', Params(expected=[Atom]))
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
