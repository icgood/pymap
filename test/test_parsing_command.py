
import unittest
from unittest.mock import MagicMock

from pymap.parsing import NotParseable
from pymap.parsing.command import *


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


class TestCommand(unittest.TestCase):

    def setUp(self):
        self.cmd = MagicMock(command=b'TEST')
        Command._commands = {b'TEST': self.cmd}

    def test_parse(self):
        self.cmd._parse.return_value = 123
        ret = Command.parse(b'a0 TEST \r\n')
        self.assertEqual(123, ret)
        self.cmd._parse.assert_called_with(b'a0', b' \r\n')

    def test_parse_failure(self):
        self.cmd._parse.side_effect = NotParseable(b'')
        with self.assertRaises(BadCommand):
            Command.parse(b'a1 TEST \r\n')
        self.cmd._parse.assert_called_with(b'a1', b' \r\n')

    def test_parse_no_command(self):
        with self.assertRaises(CommandNotFound) as exc:
            Command.parse(b'a1\r\n')
        self.assertEqual(b'a1', exc.exception.tag)
        self.assertIsNone(exc.exception.command)

    def test_parse_command_not_found(self):
        with self.assertRaises(CommandNotFound):
            Command.parse(b'a2 BADCMD \r\n')


class TestCommandNoArgs(unittest.TestCase):

    def test_parse(self):
        ret, buf = CommandNoArgs._parse(b'a0', b'    \r\n test')
        self.assertIsInstance(ret, CommandNoArgs)
        self.assertEqual(b' test', buf)

    def test_parse_no_cr(self):
        ret, buf = CommandNoArgs._parse(b'a1', b'    \n test')
        self.assertIsInstance(ret, CommandNoArgs)
        self.assertEqual(b' test', buf)
