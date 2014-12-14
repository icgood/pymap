
import unittest

from pymap.parsing.primitives import *


class TestPrimitive(unittest.TestCase):

    def test_try_parse(self):
        nil, _ = Primitive.try_parse(b'nil')
        self.assertIsInstance(nil, Nil)
        num, _ = Primitive.try_parse(b'123')
        self.assertIsInstance(num, Number)
        atom, _ = Primitive.try_parse(b'ATOM')
        self.assertIsInstance(atom, Atom)
        qstr, _ = Primitive.try_parse(b'"test"')
        self.assertIsInstance(qstr, QuotedString)
        lstr, _ = Primitive.try_parse(b'{0}\n')
        self.assertIsInstance(lstr, LiteralString)
        list, _ = Primitive.try_parse(b'()')
        self.assertIsInstance(list, List)

    def test_try_parse_expectation(self):
        with self.assertRaises(NotParseable):
            Primitive.try_parse(b'123', expected=[Atom, Nil])
        with self.assertRaises(NotParseable):
            Primitive.try_parse(b'NIL', expected=[Atom, Number])
        with self.assertRaises(NotParseable):
            Primitive.try_parse(b'ATOM', expected=[Number, Nil])


class TestNil(unittest.TestCase):

    def test_try_parse(self):
        ret, end = Nil.try_parse(b'  nil  ')
        self.assertIsInstance(ret, Nil)
        self.assertIsNone(ret.value)
        self.assertEqual(5, end)

    def test_try_parse_failure(self):
        with self.assertRaises(NotParseable):
            Nil.try_parse(b'')
        with self.assertRaises(NotParseable):
            Nil.try_parse(b'niltest')

    def test_bytes(self):
        nil = Nil()
        self.assertEqual(b'NIL', bytes(nil))


class TestNumber(unittest.TestCase):

    def test_try_parse(self):
        ret, end = Number.try_parse(b'  123  ')
        self.assertIsInstance(ret, Number)
        self.assertEqual(123, ret.value)
        self.assertEqual(5, end)

    def test_try_parse_failure(self):
        with self.assertRaises(NotParseable):
            Number.try_parse(b'abc')
        with self.assertRaises(NotParseable):
            Number.try_parse(b'123abc')

    def test_bytes(self):
        nil = Number(456)
        self.assertEqual(b'456', bytes(nil))


class TestAtom(unittest.TestCase):

    def test_try_parse(self):
        ret, end = Atom.try_parse(b'  AtoM asdf  ')
        self.assertIsInstance(ret, Atom)
        self.assertEqual(b'AtoM', ret.value)
        self.assertEqual(6, end)

    def test_try_parse_failure(self):
        with self.assertRaises(NotParseable):
            Atom.try_parse(b'{}')
        with self.assertRaises(NotParseable):
            Atom.try_parse(b'NIL')
        with self.assertRaises(NotParseable):
            Atom.try_parse(b'123')

    def test_bytes(self):
        nil = Atom(b'TEST.STUFF:asdf')
        self.assertEqual(b'TEST.STUFF:asdf', bytes(nil))


class TestQuotedString(unittest.TestCase):

    def test_try_parse(self):
        ret, end = String.try_parse(rb'  "one\"two\\three"  ')
        self.assertIsInstance(ret, QuotedString)
        self.assertEqual(rb'one"two\three', ret.value)
        self.assertEqual(19, end)

    def test_try_parse_empty(self):
        ret, end = String.try_parse(rb'  ""  ')
        self.assertIsInstance(ret, QuotedString)
        self.assertEqual(rb'', ret.value)
        self.assertEqual(4, end)

    def test_try_parse_failure(self):
        with self.assertRaises(NotParseable):
            String.try_parse(b'test')
        with self.assertRaises(NotParseable):
            String.try_parse(b'"one\r\ntwo"')
        with self.assertRaises(NotParseable):
            String.try_parse(rb'"one\ two"')
        with self.assertRaises(NotParseable):
            String.try_parse(b'"test')

    def test_bytes(self):
        qstring1 = QuotedString(b'one"two\\three')
        self.assertEqual(b'"one\\"two\\\\three"', bytes(qstring1))
        qstring2 = QuotedString(b'test', b'"asdf"')
        self.assertEqual(b'"asdf"', bytes(qstring2))


class TestLiteralString(unittest.TestCase):

    def test_try_parse(self):
        ret, end = String.try_parse(b'  {5}\r\nte\x01st...  ')
        self.assertIsInstance(ret, LiteralString)
        self.assertEqual(b'te\x01st', ret.value)
        self.assertEqual(12, end)

    def test_try_parse_empty(self):
        ret, end = String.try_parse(b'  {0}\n...  ')
        self.assertIsInstance(ret, LiteralString)
        self.assertEqual(b'', ret.value)
        self.assertEqual(6, end)

    def test_try_parse_failure(self):
        with self.assertRaises(NotParseable):
            String.try_parse(b'{}\r\n')
        with self.assertRaises(NotParseable):
            String.try_parse(b'{1000}\r\n'+b'*'*999)

    def test_bytes(self):
        qstring1 = LiteralString(b'one\r\ntwo')
        self.assertEqual(b'{8}\r\none\r\ntwo', bytes(qstring1))
        qstring2 = LiteralString(b'test', b'{0}\r\n')
        self.assertEqual(b'{0}\r\n', bytes(qstring2))


class TestList(unittest.TestCase):

    def test_try_parse(self):
        ret, end = List.try_parse(b'  (ONE 2 (NIL) "four" {5}\r\nfive!)  ')
        self.assertIsInstance(ret, List)
        self.assertEqual(5, len(ret.value))
        self.assertEqual(33, end)
        self.assertIsInstance(ret.value[0], Atom)
        self.assertEqual(b'ONE', ret.value[0].value)
        self.assertIsInstance(ret.value[1], Number)
        self.assertEqual(2, ret.value[1].value)
        self.assertIsInstance(ret.value[2], List)
        self.assertIsNone(ret.value[2].value[0].value)
        self.assertIsInstance(ret.value[3], QuotedString)
        self.assertEqual(b'four', ret.value[3].value)
        self.assertIsInstance(ret.value[4], LiteralString)
        self.assertEqual(b'five!', ret.value[4].value)

    def test_try_parse_empty(self):
        ret, end = List.try_parse(rb'  ()  ')
        self.assertIsInstance(ret, List)
        self.assertEqual([], ret.value)
        self.assertEqual(4, end)

    def test_try_parse_failure(self):
        with self.assertRaises(NotParseable):
            List.try_parse(b'{}')
        with self.assertRaises(NotParseable):
            List.try_parse(b'("one"TWO)')
