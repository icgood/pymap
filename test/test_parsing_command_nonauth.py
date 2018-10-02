
import unittest

from pymap.parsing import Params
from pymap.parsing.command.nonauth import AuthenticateCommand, LoginCommand


class TestAuthenticateCommand(unittest.TestCase):

    def test_parse(self):
        ret, buf = AuthenticateCommand.parse(b' PLAIN\n  ', Params())
        self.assertEqual(b'PLAIN', ret.mech_name)
        self.assertEqual(b'  ', buf)


class TestLoginCommand(unittest.TestCase):

    def test_parse(self):
        ret, buf = LoginCommand.parse(b' one two\n  ', Params())
        self.assertEqual(b'one', ret.userid)
        self.assertEqual(b'two', ret.password)
        self.assertEqual(b'  ', buf)
