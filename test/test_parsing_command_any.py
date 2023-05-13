
import unittest

from pymap.parsing import Params
from pymap.parsing.exceptions import NotParseable
from pymap.parsing.command.any import IdCommand


class TestIdCommand(unittest.TestCase):

    def test_parse_nil(self) -> None:
        ret, buf = IdCommand.parse(
            memoryview(b' NIL\n  '),
            Params())
        self.assertIsNone(ret.parameters)
        self.assertEqual(b'  ', buf)

    def test_parse_empty(self) -> None:
        ret, buf = IdCommand.parse(
            memoryview(b' ()\n  '),
            Params())
        self.assertEqual({}, ret.parameters)
        self.assertEqual(b'  ', buf)

    def test_parse(self) -> None:
        ret, buf = IdCommand.parse(
            memoryview(b' ("one" "two" "three" "four")\n  '),
            Params())
        print(repr(ret.parameters))
        self.assertEqual({b'one': b'two', b'three': b'four'}, ret.parameters)
        self.assertEqual(b'  ', buf)

    def test_parse_odd(self) -> None:
        with self.assertRaises(NotParseable):
            IdCommand.parse(
                memoryview(b' ("foo")\n  '),
                Params())
