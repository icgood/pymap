
import unittest

from pymap.parsing import NotParseable, RequiresContinuation
from pymap.parsing.primitives import *


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

    def test_instantiate(self):
        with self.assertRaises(NotImplementedError):
            String()

    def test_quoted_parse(self):
        ret, buf = String.parse(br'  "one\"two\\three"  ')
        self.assertIsInstance(ret, QuotedString)
        self.assertEqual(br'one"two\three', ret.value)
        self.assertEqual(b'  ', buf)

    def test_quoted_parse_empty(self):
        ret, buf = String.parse(br'  ""  ')
        self.assertIsInstance(ret, QuotedString)
        self.assertEqual(br'', ret.value)
        self.assertEqual(b'  ', buf)

    def test_quoted_parse_failure(self):
        with self.assertRaises(NotParseable):
            String.parse(b'test')
        with self.assertRaises(NotParseable):
            String.parse(b'"one\r\ntwo"')
        with self.assertRaises(NotParseable):
            String.parse(br'"one\ two"')
        with self.assertRaises(NotParseable):
            String.parse(b'"test')

    def test_quoted_bytes(self):
        qstring1 = QuotedString(b'one"two\\three')
        self.assertEqual(b'"one\\"two\\\\three"', bytes(qstring1))
        qstring2 = QuotedString(b'test', b'"asdf"')
        self.assertEqual(b'"asdf"', bytes(qstring2))

    def test_literal_parse(self):
        ret, buf = String.parse(b'{5}\r\n', continuations=[b'test\x01abc'])
        self.assertIsInstance(ret, LiteralString)
        self.assertEqual(b'test\x01', ret.value)
        self.assertEqual(b'abc', buf)

    def test_literal_parse_empty(self):
        ret, buf = String.parse(b'{0}\r\n', continuations=[b'abc'])
        self.assertIsInstance(ret, LiteralString)
        self.assertEqual(b'', ret.value)
        self.assertEqual(b'abc', buf)

    def test_literal_parse_failure(self):
        with self.assertRaises(NotParseable):
            String.parse(b'{}\r\n')
        with self.assertRaises(NotParseable):
            String.parse(b'{10}')
        with self.assertRaises(RequiresContinuation):
            String.parse(b'{10}\r\n')
        with self.assertRaises(NotParseable):
            String.parse(b'{10}\r\n', continuations=[b'a'*9])

    def test_literal_bytes(self):
        qstring1 = LiteralString(b'one\r\ntwo')
        self.assertEqual(b'{8}\r\none\r\ntwo', bytes(qstring1))
        qstring2 = LiteralString(b'')
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
        ret, buf = List.parse(br'  ()  ')
        self.assertIsInstance(ret, List)
        self.assertEqual([], ret.value)
        self.assertEqual(b'  ', buf)

    def test_parse_failure(self):
        with self.assertRaises(NotParseable):
            List.parse(b'{}')
        with self.assertRaises(NotParseable):
            List.parse(b'("one"TWO)')

    def test_bytes(self):
        ret = List([QuotedString(b'abc'), Number(123), List([Nil()])])
        self.assertEqual(b'("abc" 123 (NIL))', bytes(ret))
