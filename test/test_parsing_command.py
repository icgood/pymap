
import unittest

from pymap.parsing.command import *  # NOQA


class TestBadCommand(unittest.TestCase):

    def test_bytes(self):
        class TestCmd(Command):
            command = b'TEST'
        exc = BadCommand(b'abc TEST stuff\r\n', b'abc', TestCmd)
        self.assertEqual(b'abc', exc.tag)
        self.assertEqual(TestCmd, exc.command)
        self.assertEqual(b'TEST: [:ERROR:]abc TEST stuff', bytes(exc))
        self.assertEqual('TEST: [:ERROR:]abc TEST stuff', str(exc))


class TestCommandNotFound(unittest.TestCase):

    def test_bytes(self):
        exc = CommandNotFound(None, None, b'TEST')
        self.assertEqual(b'Command Not Found: TEST', bytes(exc))

    def test_no_command(self):
        exc = CommandNotFound(None, None)
        self.assertEqual(b'Command Not Given', bytes(exc))
        self.assertEqual('Command Not Given', str(exc))


class TestCommandNoArgs(unittest.TestCase):

    def test_parse(self):
        ret, buf = CommandNoArgs.parse(b'    \r\n test')
        self.assertIsInstance(ret, CommandNoArgs)
        self.assertEqual(b' test', buf)

    def test_parse_no_cr(self):
        ret, buf = CommandNoArgs.parse(b'    \n test')
        self.assertIsInstance(ret, CommandNoArgs)
        self.assertEqual(b' test', buf)


class TestCommands(unittest.TestCase):

    def setUp(self):
        self.commands = Commands()

    def test_parse(self):
        cmd, buf = self.commands.parse(b'a0 NOOP\n  ')
        self.assertIsInstance(cmd, Command)
        self.assertEqual(b'a0', cmd.tag)
        self.assertEqual(b'  ', buf)
