
import unittest

from pymap.parsing import NotParseable
from pymap.parsing.primitives import *


class TestPrimitive(unittest.TestCase):

    def test_parse(self):
        nil, _ = Primitive.parse(b'nil')
        self.assertIsInstance(nil, Nil)
        num, _ = Primitive.parse(b'123')
        self.assertIsInstance(num, Number)
        atom, _ = Primitive.parse(b'ATOM')
        self.assertIsInstance(atom, Atom)
        qstr, _ = Primitive.parse(b'"test"')
        self.assertIsInstance(qstr, QuotedString)
        list, _ = Primitive.parse(b'()')
        self.assertIsInstance(list, List)

    def test_parse_expectation(self):
        with self.assertRaises(NotParseable):
            Primitive.parse(b'123', expected=[Atom, Nil])
        with self.assertRaises(NotParseable):
            Primitive.parse(b'NIL', expected=[Atom, Number])
        with self.assertRaises(NotParseable):
            Primitive.parse(b'ATOM', expected=[Number, Nil])


class TestNil(unittest.TestCase):

    def test_parse(self):
        ret, buf = Nil.parse(b'  nil  ')
        self.assertIsInstance(ret, Nil)
        self.assertIsNone(ret.value)
        self.assertEqual(b'  ', buf)

    def test_parse_failure(self):
        with self.assertRaises(NotParseable):
            Nil.parse(b'')
        with self.assertRaises(NotParseable):
            Nil.parse(b'niltest')

    def test_bytes(self):
        nil = Nil()
        self.assertEqual(b'NIL', bytes(nil))


class TestNumber(unittest.TestCase):

    def test_parse(self):
        ret, buf = Number.parse(b'  123  ')
        self.assertIsInstance(ret, Number)
        self.assertEqual(123, ret.value)
        self.assertEqual(b'  ', buf)

    def test_parse_failure(self):
        with self.assertRaises(NotParseable):
            Number.parse(b'abc')
        with self.assertRaises(NotParseable):
            Number.parse(b'123abc')

    def test_bytes(self):
        nil = Number(456)
        self.assertEqual(b'456', bytes(nil))


class TestAtom(unittest.TestCase):

    def test_parse(self):
        ret, buf = Atom.parse(b'  AtoM asdf  ')
        self.assertIsInstance(ret, Atom)
        self.assertEqual(b'AtoM', ret.value)
        self.assertEqual(b' asdf  ', buf)

    def test_parse_failure(self):
        with self.assertRaises(NotParseable):
            Atom.parse(b'{}')
        with self.assertRaises(NotParseable):
            Atom.parse(b'NIL')
        with self.assertRaises(NotParseable):
            Atom.parse(b'123')

    def test_bytes(self):
        nil = Atom(b'TEST.STUFF:asdf')
        self.assertEqual(b'TEST.STUFF:asdf', bytes(nil))


class TestQuotedString(unittest.TestCase):

    def test_parse(self):
        ret, buf = String.parse(rb'  "one\"two\\three"  ')
        self.assertIsInstance(ret, QuotedString)
        self.assertEqual(rb'one"two\three', ret.value)
        self.assertEqual(b'  ', buf)

    def test_parse_empty(self):
        ret, buf = String.parse(rb'  ""  ')
        self.assertIsInstance(ret, QuotedString)
        self.assertEqual(rb'', ret.value)
        self.assertEqual(b'  ', buf)

    def test_parse_failure(self):
        with self.assertRaises(NotParseable):
            String.parse(b'test')
        with self.assertRaises(NotParseable):
            String.parse(b'"one\r\ntwo"')
        with self.assertRaises(NotParseable):
            String.parse(rb'"one\ two"')
        with self.assertRaises(NotParseable):
            String.parse(b'"test')

    def test_bytes(self):
        qstring1 = QuotedString(b'one"two\\three')
        self.assertEqual(b'"one\\"two\\\\three"', bytes(qstring1))
        qstring2 = QuotedString(b'test', b'"asdf"')
        self.assertEqual(b'"asdf"', bytes(qstring2))


class TestLiteralString(unittest.TestCase):

    def test_parse(self):
        assert False

    def test_parse_empty(self):
        assert False

    def test_parse_failure(self):
        with self.assertRaises(NotParseable):
            String.parse(b'{}\r\n')
        with self.assertRaises(NotParseable):
            String.parse(b'{10}')

    def test_bytes(self):
        qstring1 = LiteralString(b'one\r\ntwo')
        self.assertEqual(b'{8}\r\none\r\ntwo', bytes(qstring1))
        qstring2 = LiteralString(b'test', b'{0}\r\n')
        self.assertEqual(b'{0}\r\n', bytes(qstring2))


class TestList(unittest.TestCase):

    def test_parse(self):
        ret, buf = List.parse(b'  (ONE 2 (NIL) "four" )  ')
        self.assertIsInstance(ret, List)
        self.assertEqual(4, len(ret.value))
        self.assertEqual(b'  ', buf)
        self.assertIsInstance(ret.value[0], Atom)
        self.assertEqual(b'ONE', ret.value[0].value)
        self.assertIsInstance(ret.value[1], Number)
        self.assertEqual(2, ret.value[1].value)
        self.assertIsInstance(ret.value[2], List)
        self.assertIsNone(ret.value[2].value[0].value)
        self.assertIsInstance(ret.value[3], QuotedString)
        self.assertEqual(b'four', ret.value[3].value)

    def test_parse_empty(self):
        ret, buf = List.parse(rb'  ()  ')
        self.assertIsInstance(ret, List)
        self.assertEqual([], ret.value)
        self.assertEqual(b'  ', buf)

    def test_parse_failure(self):
        with self.assertRaises(NotParseable):
            List.parse(b'{}')
        with self.assertRaises(NotParseable):
            List.parse(b'("one"TWO)')
