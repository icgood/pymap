
import unittest
from datetime import datetime, timezone, timedelta

from pymap.parsing import NotParseable
from pymap.parsing.specials import *


class TestAString(unittest.TestCase):

    def test_parse(self):
        ret, buf = AString.parse(b'  a001[+]  ')
        self.assertIsInstance(ret, AString)
        self.assertEqual(b'a001[+]', ret.value)
        self.assertEqual(b'  ', buf)

    def test_parse_quoted(self):
        ret, buf = AString.parse(br'  "a bc \" d"  ')
        self.assertIsInstance(ret, AString)
        self.assertEqual(b'a bc " d', ret.value)
        self.assertEqual(b'  ', buf)

    def test_parse_literal(self):
        ret, buf = AString.parse(b'  {4}\r\n', continuations=[b'abcd  '])
        self.assertIsInstance(ret, AString)
        self.assertEqual(b'abcd', ret.value)
        self.assertEqual(b'  ', buf)

    def test_bytes(self):
        a1 = AString(b'abc123')
        self.assertEqual(b'abc123', bytes(a1))
        a2 = AString(b' a (b) c ')
        self.assertEqual(b'" a (b) c "', bytes(a2))
        self.assertEqual(b'" a (b) c "', bytes(a2))


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


class TestDateTime(unittest.TestCase):

    def test_parse(self):
        ret, buf = DateTime.parse(b'"1-Jan-2000 01:02:03 +0500"')
        self.assertIsInstance(ret, DateTime)
        self.assertEqual(1, ret.when.day)
        self.assertEqual(1, ret.when.month)
        self.assertEqual(2000, ret.when.year)
        self.assertEqual(1, ret.when.hour)
        self.assertEqual(2, ret.when.minute)
        self.assertEqual(3, ret.when.second)
        self.assertEqual(18000.0, ret.when.utcoffset().total_seconds())

    def test_parse_failure(self):
        with self.assertRaises(InvalidContent):
            DateTime.parse(b'"test"')

    def test_bytes(self):
        dt1 = DateTime(datetime(2000, 1, 1, 1, 2, 3,
                                tzinfo=timezone(timedelta(hours=5))))
        self.assertEqual(b'"01-Jan-2000 01:02:03 +0500"', bytes(dt1))
        dt2 = DateTime(None, b'testing')
        self.assertEqual(b'"testing"', bytes(dt2))
