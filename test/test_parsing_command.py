
import unittest
from unittest.mock import MagicMock

from pymap.parsing import NotParseable
from pymap.parsing.command import *


class TestCommand(unittest.TestCase):

    def setUp(self):
        from pymap.parsing.command import any, auth, nonauth, select
        self.cmd = MagicMock(command=b'TEST', regex=None)
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
