
import unittest

from pymap.parsing import Params
from pymap.parsing.command import Command, CommandNoArgs
from pymap.parsing.commands import Commands


class TestCommandNoArgs(unittest.TestCase):

    def test_parse(self):
        ret, buf = CommandNoArgs.parse(b'    \r\n test', Params())
        self.assertIsInstance(ret, CommandNoArgs)
        self.assertEqual(b' test', buf)

    def test_parse_no_cr(self):
        ret, buf = CommandNoArgs.parse(b'    \n test', Params())
        self.assertIsInstance(ret, CommandNoArgs)
        self.assertEqual(b' test', buf)


class TestCommands(unittest.TestCase):

    def setUp(self):
        self.commands = Commands()

    def test_parse(self):
        cmd, buf = self.commands.parse(b'a0 NOOP\n  ', Params())
        self.assertIsInstance(cmd, Command)
        self.assertEqual(b'a0', cmd.tag)
        self.assertEqual(b'  ', buf)
