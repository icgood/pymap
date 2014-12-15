
import unittest

from pymap.parsing import NotParseable
from pymap.parsing.specials import *


class TestMailbox(unittest.TestCase):

    def test_parse(self):
        ret, buf = Mailbox.parse(b'  \xc9\x91\xc6\xa8\xc6\x8c\xc6\x92  ')
        self.assertIsInstance(ret, Mailbox)
        self.assertEqual('ɑƨƌƒ', ret.value)
        self.assertEqual(b'  ', buf)

    def test_parse_inbox(self):
        ret, buf = Mailbox.parse(b'  iNbOx  ')
        self.assertIsInstance(ret, Mailbox)
        self.assertEqual('INBOX', ret.value)
        self.assertEqual(b'  ', buf)

    def test_parse_failure(self):
        with self.assertRaises(NotParseable):
            Mailbox.parse(b'  ')

    def test_bytes(self):
        mbx = Mailbox('ɑƨƌƒ')
        self.assertEqual(b'\xc9\x91\xc6\xa8\xc6\x8c\xc6\x92', bytes(mbx))
