
import unittest

from pymap.parsing import Params
from pymap.parsing.command import Command, CommandNoArgs
from pymap.parsing.commands import Commands
from pymap.parsing.exceptions import CommandNotFound, CommandInvalid, \
    NotParseable


class TestCommandInvalid(unittest.TestCase):

    def test_bytes(self):
        try:
            try:
                raise NotParseable(b'abc TEST stuff')
            except NotParseable as cause:
                raise CommandInvalid(b'abc', b'TEST') from cause
        except CommandInvalid as exc:
            self.assertEqual(b'abc', exc.tag)
            self.assertEqual(b'TEST', exc.command)
            self.assertEqual(b'TEST: [:ERROR:]abc TEST stuff', bytes(exc))
            self.assertEqual('TEST: [:ERROR:]abc TEST stuff', str(exc))


class TestCommandNotFound(unittest.TestCase):

    def test_bytes(self):
        exc = CommandNotFound(b'', b'TEST')
        self.assertEqual(b'Command Not Found: TEST', bytes(exc))

    def test_no_command(self):
        exc = CommandNotFound(b'')
        self.assertEqual(b'Command Not Given', bytes(exc))
        self.assertEqual('Command Not Given', str(exc))


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
