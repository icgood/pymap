
import unittest

from pymap.parsing import Params
from pymap.parsing.exceptions import NotParseable, RequiresContinuation
from pymap.parsing.primitives import Nil, Number, Atom, String, QuotedString, \
    LiteralString, ListP


class TestNil(unittest.TestCase):

    def test_parse(self):
        ret, buf = Nil.parse(b'  nil  ', Params())
        self.assertIsInstance(ret, Nil)
        self.assertIsNone(ret.value)
        self.assertEqual(b'  ', buf)

    def test_parse_failure(self):
        with self.assertRaises(NotParseable):
            Nil.parse(b'', Params())
        with self.assertRaises(NotParseable):
            Nil.parse(b'niltest', Params())

    def test_bytes(self):
        nil = Nil()
        self.assertEqual(b'NIL', bytes(nil))


class TestNumber(unittest.TestCase):

    def test_parse(self):
        ret, buf = Number.parse(b'  123  ', Params())
        self.assertIsInstance(ret, Number)
        self.assertEqual(123, ret.value)
        self.assertEqual(b'  ', buf)

    def test_parse_failure(self):
        with self.assertRaises(NotParseable):
            Number.parse(b'abc', Params())
        with self.assertRaises(NotParseable):
            Number.parse(b'123abc', Params())

    def test_bytes(self):
        nil = Number(456)
        self.assertEqual(b'456', bytes(nil))


class TestAtom(unittest.TestCase):

    def test_parse(self):
        ret, buf = Atom.parse(b'  AtoM asdf  ', Params())
        self.assertIsInstance(ret, Atom)
        self.assertEqual(b'AtoM', ret.value)
        self.assertEqual(b' asdf  ', buf)

    def test_parse_failure(self):
        with self.assertRaises(NotParseable):
            Atom.parse(b'{}', Params())

    def test_bytes(self):
        nil = Atom(b'TEST.STUFF:asdf')
        self.assertEqual(b'TEST.STUFF:asdf', bytes(nil))


class TestString(unittest.TestCase):

    def test_quoted_parse(self):
        ret, buf = String.parse(br'  "one\"two\\three"  ', Params())
        self.assertIsInstance(ret, QuotedString)
        self.assertEqual(br'one"two\three', ret.value)
        self.assertEqual(b'  ', buf)

    def test_quoted_parse_empty(self):
        ret, buf = String.parse(br'  ""  ', Params())
        self.assertIsInstance(ret, QuotedString)
        self.assertEqual(br'', ret.value)
        self.assertEqual(b'  ', buf)

    def test_quoted_parse_failure(self):
        with self.assertRaises(NotParseable):
            String.parse(b'test', Params())
        with self.assertRaises(NotParseable):
            String.parse(b'"one\r\ntwo"', Params())
        with self.assertRaises(NotParseable):
            String.parse(br'"one\ two"', Params())
        with self.assertRaises(NotParseable):
            String.parse(b'"test', Params())

    def test_quoted_bytes(self):
        qstring1 = QuotedString(b'one"two\\three')
        self.assertEqual(b'"one\\"two\\\\three"', bytes(qstring1))
        qstring2 = QuotedString(b'test', b'"asdf"')
        self.assertEqual(b'"asdf"', bytes(qstring2))

    def test_literal_parse(self):
        ret, buf = String.parse(
            b'{5}\r\n', Params(continuations=[b'test\x01abc']))
        self.assertIsInstance(ret, LiteralString)
        self.assertEqual(b'test\x01', ret.value)
        self.assertEqual(b'abc', buf)

    def test_literal_parse_empty(self):
        ret, buf = String.parse(
            b'{0}\r\n', Params(continuations=[b'abc']))
        self.assertIsInstance(ret, LiteralString)
        self.assertEqual(b'', ret.value)
        self.assertEqual(b'abc', buf)

    def test_literal_parse_failure(self):
        with self.assertRaises(NotParseable):
            String.parse(b'{}\r\n', Params())
        with self.assertRaises(NotParseable):
            String.parse(b'{10}', Params())
        with self.assertRaises(NotParseable):
            String.parse(b'{10}\r\nabc', Params())
        with self.assertRaises(RequiresContinuation):
            String.parse(b'{10}\r\n', Params())
        with self.assertRaises(NotParseable):
            String.parse(b'{10}\r\n', Params(continuations=[b'a'*9]))
        with self.assertRaises(NotParseable):
            String.parse(b'{10+}\r\n', Params())
        with self.assertRaises(NotParseable) as raised:
            String.parse(b'{4097}\r\n', Params())
        self.assertEqual(b'[TOOBIG]', bytes(raised.exception.code))

    def test_literal_bytes(self):
        qstring1 = LiteralString(b'one\r\ntwo')
        self.assertEqual(b'{8}\r\none\r\ntwo', bytes(qstring1))
        qstring2 = LiteralString(b'')
        self.assertEqual(b'{0}\r\n', bytes(qstring2))


class TestList(unittest.TestCase):

    def test_parse(self):
        ret, buf = ListP.parse(
            b'  (ONE 2 (NIL) "four" )  ',
            Params(list_expected=[Nil, Number, Atom, String, ListP]))
        self.assertIsInstance(ret, ListP)
        self.assertEqual(4, len(ret.value))
        self.assertEqual(b'  ', buf)
        self.assertIsInstance(ret.value[0], Atom)
        self.assertEqual(b'ONE', ret.value[0].value)
        self.assertIsInstance(ret.value[1], Number)
        self.assertEqual(2, ret.value[1].value)
        self.assertIsInstance(ret.value[2], ListP)
        self.assertIsNone(ret.value[2].value[0].value)
        self.assertIsInstance(ret.value[3], QuotedString)
        self.assertEqual(b'four', ret.value[3].value)

    def test_parse_empty(self):
        ret, buf = ListP.parse(br'  ()  ', Params())
        self.assertIsInstance(ret, ListP)
        self.assertEqual([], ret.value)
        self.assertEqual(b'  ', buf)

    def test_parse_failure(self):
        with self.assertRaises(NotParseable):
            ListP.parse(b'{}', Params())
        with self.assertRaises(NotParseable):
            ListP.parse(b'("one"TWO)', Params(list_expected=[Atom, String]))
        with self.assertRaises(NotParseable):
            ListP.parse(b'(123 abc 456)', Params(list_expected=[Number]))

    def test_bytes(self):
        ret = ListP([QuotedString(b'abc'), Number(123), ListP([Nil()])])
        self.assertEqual(b'("abc" 123 (NIL))', bytes(ret))
