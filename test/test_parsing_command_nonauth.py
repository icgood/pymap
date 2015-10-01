
import unittest

from pymap.parsing.command import *  # NOQA
from pymap.parsing.command.nonauth import *  # NOQA


class TestAuthenticateCommand(unittest.TestCase):

    def test_parse(self):
        ret, buf = AuthenticateCommand._parse(b'tag', b' PLAIN\n  ')
        self.assertEqual(b'tag', ret.tag)
        self.assertEqual(b'PLAIN', ret.mech_name)
        self.assertEqual(b'  ', buf)


class TestLoginCommand(unittest.TestCase):

    def test_parse(self):
        ret, buf = LoginCommand._parse(b'tag', b' one two\n  ')
        self.assertEqual(b'tag', ret.tag)
        self.assertEqual(b'one', ret.userid)
        self.assertEqual(b'two', ret.password)
        self.assertEqual(b'  ', buf)
