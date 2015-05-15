
import unittest
from unittest.mock import patch, MagicMock

from pysasl import ServerMechanism

from pymap.parsing import NotParseable
from pymap.parsing.command import *  # NOQA
from pymap.parsing.command.nonauth import *  # NOQA


class TestAuthenticateCommand(unittest.TestCase):

    @patch.object(ServerMechanism, 'get_available')
    def test_parse(self, get_mock):
        plain_mock = MagicMock()
        get_mock.return_value = {'PLAIN': plain_mock}
        ret, buf = AuthenticateCommand._parse(b'tag', b' PLAIN\n  ')
        self.assertEqual(b'tag', ret.tag)
        self.assertEqual(plain_mock(), ret.mech)
        self.assertEqual(b'  ', buf)

    @patch.object(ServerMechanism, 'get_available')
    def test_parse_error(self, get_mock):
        get_mock.return_value = {}
        with self.assertRaises(NotParseable):
            AuthenticateCommand._parse(b'tag', b' PLAIN\n  ')


class TestLoginCommand(unittest.TestCase):

    def test_parse(self):
        ret, buf = LoginCommand._parse(b'tag', b' one two\n  ')
        self.assertEqual(b'tag', ret.tag)
        self.assertEqual(b'one', ret.userid)
        self.assertEqual(b'two', ret.password)
        self.assertEqual(b'  ', buf)
