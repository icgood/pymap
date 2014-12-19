
import unittest

from pymap.parsing import NotParseable
from pymap.parsing.specials import *


class TestTag(unittest.TestCase):

    def test_parse(self):
        ret, buf = Tag.parse(b' a[001]  ')
        self.assertIsInstance(ret, Tag)
        self.assertEqual(b'a[001]', ret.value)
        self.assertEqual(b'  ', buf)

    def test_parse_failure(self):
        with self.assertRaises(NotParseable):
            Tag.parse(b'')

    def test_bytes(self):
        tag1 = Tag(b'a[001]')
        self.assertEqual(b'a[001]', bytes(tag1))


class TestMailbox(unittest.TestCase):

    def test_parse(self):
        ret, buf = Mailbox.parse(b'~peter/mail/&-/&U,BTFw-/&ZeVnLIqe-')
        self.assertIsInstance(ret, Mailbox)
        self.assertEqual('~peter/mail/&/台北/日本語', ret.value)
        self.assertEqual(b'', buf)

    def test_parse_inbox(self):
        ret, buf = Mailbox.parse(b'  iNbOx  ')
        self.assertIsInstance(ret, Mailbox)
        self.assertEqual('INBOX', ret.value)
        self.assertEqual(b'  ', buf)

    def test_parse_quoted(self):
        ret, buf = Mailbox.parse(b'  "test mailbox \\"stuff\\""  ')
        self.assertIsInstance(ret, Mailbox)
        self.assertEqual('test mailbox "stuff"', ret.value)
        self.assertEqual(b'  ', buf)

    def test_parse_failure(self):
        with self.assertRaises(NotParseable):
            Mailbox.parse(b'  ')

    def test_bytes(self):
        mbx = Mailbox('~peter/mail/&/台北/日本語')
        self.assertEqual(b'~peter/mail/&-/&U,BTFw-/&ZeVnLIqe-', bytes(mbx))
