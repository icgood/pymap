
import unittest

from pymap.parsing import Params
from pymap.parsing.exceptions import NotParseable
from pymap.parsing.primitives import Nil, Number, Atom, String, QuotedString, \
    LiteralString, List
from pymap.parsing.state import ParsingState, ParsingInterrupt, \
    ExpectContinuation


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
        state = ParsingState(continuations=[b'test\x01abc'])
        ret, buf = String.parse(b'{5}\r\n', Params(state))
        self.assertIsInstance(ret, LiteralString)
        self.assertEqual(b'test\x01', ret.value)
        self.assertFalse(ret.binary)
        self.assertEqual(b'abc', buf)

    def test_literal_parse_empty(self):
        state = ParsingState(continuations=[b'abc'])
        ret, buf = String.parse(b'{0}\r\n', Params(state))
        self.assertIsInstance(ret, LiteralString)
        self.assertEqual(b'', ret.value)
        self.assertEqual(b'abc', buf)

    def test_literal_plus(self):
        ret, buf = String.parse(b'{5+}\r\ntest\x01abc', Params())
        self.assertIsInstance(ret, LiteralString)
        self.assertEqual(b'test\x01', ret.value)
        self.assertFalse(ret.binary)
        self.assertEqual(b'abc', buf)

    def test_literal_binary(self):
        state = ParsingState(continuations=[b'\x00\x01\02abc'])
        ret, buf = String.parse(b'~{3}\r\n', Params(state))
        self.assertIsInstance(ret, LiteralString)
        self.assertEqual(b'\x00\x01\x02', ret.value)
        self.assertTrue(ret.binary)
        self.assertEqual(b'abc', buf)

    def test_literal_plus_binary(self):
        ret, buf = String.parse(b'~{3+}\r\n\x00\x01\02abc', Params())
        self.assertIsInstance(ret, LiteralString)
        self.assertEqual(b'\x00\x01\x02', ret.value)
        self.assertTrue(ret.binary)
        self.assertEqual(b'abc', buf)

    def test_literal_parse_failure(self):
        with self.assertRaises(NotParseable):
            String.parse(b'{}\r\n', Params())
        with self.assertRaises(NotParseable):
            String.parse(b'{10}', Params())
        with self.assertRaises(NotParseable):
            String.parse(b'{10}\r\nabc', Params())
        with self.assertRaises(NotParseable):
            state = ParsingState(continuations=[b'a'*9])
            String.parse(b'{10}\r\n', Params(state))
        with self.assertRaises(NotParseable):
            String.parse(b'{10+}\r\n' + (b'a'*9), Params())
        with self.assertRaises(ParsingInterrupt) as raised1:
            String.parse(b'{10}\r\n', Params())
        self.assertIsInstance(raised1.exception.expected, ExpectContinuation)
        with self.assertRaises(NotParseable) as raised2:
            String.parse(b'{4097}\r\n', Params())
        self.assertEqual(b'[TOOBIG]', bytes(raised2.exception.code))

    def test_literal_bytes(self):
        qstring1 = LiteralString(b'one\r\ntwo')
        self.assertEqual(b'{8}\r\none\r\ntwo', bytes(qstring1))
        qstring2 = LiteralString(b'')
        self.assertEqual(b'{0}\r\n', bytes(qstring2))

    def test_build_binary(self):
        ret = String.build(b'\x00\x01', True)
        self.assertEqual(b'\x00\x01', ret.value)
        self.assertTrue(ret.binary)
        self.assertEqual(b'~{2}\r\n\x00\x01', bytes(ret))


class TestList(unittest.TestCase):

    def test_parse(self):
        ret, buf = List.parse(
            b'  (ONE 2 (NIL) "four" )  ',
            Params(list_expected=[Nil, Number, Atom, String, List]))
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
        ret, buf = List.parse(br'  ()  ', Params())
        self.assertIsInstance(ret, List)
        self.assertEqual([], ret.value)
        self.assertEqual(b'  ', buf)

    def test_parse_failure(self):
        with self.assertRaises(NotParseable):
            List.parse(b'{}', Params())
        with self.assertRaises(NotParseable):
            List.parse(b'("one"TWO)', Params(list_expected=[Atom, String]))
        with self.assertRaises(NotParseable):
            List.parse(b'(123 abc 456)', Params(list_expected=[Number]))

    def test_bytes(self):
        ret = List([QuotedString(b'abc'), Number(123), List([Nil()])])
        self.assertEqual(b'("abc" 123 (NIL))', bytes(ret))
