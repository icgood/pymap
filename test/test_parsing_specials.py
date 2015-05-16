
import unittest
from datetime import datetime, timezone, timedelta

from pymap.parsing import NotParseable, UnexpectedType
from pymap.parsing.specials import *  # NOQA


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
        self.assertEqual(b'~peter/mail/&-/&U,BTFw-/&ZeVnLIqe-', bytes(mbx))

    def test_str(self):
        mbx = Mailbox('~peter/mail/&/台北/日本語')
        self.assertEqual('~peter/mail/&/台北/日本語', str(mbx))


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


class TestFlag(unittest.TestCase):

    def test_parse(self):
        ret1, buf1 = Flag.parse(br'MyFlag  \Seen  ')
        self.assertEqual(b'MyFlag', ret1.value)
        self.assertEqual(br'  \Seen  ', buf1)
        ret2, buf2 = Flag.parse(buf1)
        self.assertEqual(br'\Seen', ret2.value)
        self.assertEqual(b'  ', buf2)

    def test_cmp(self):
        f1 = Flag(br'\Flag1')
        f2 = Flag(br'\Flag2')
        f3 = Flag(br'\Flag1')
        self.assertEqual(f1, f3)
        self.assertEqual(f1, br'\Flag1')
        self.assertNotEqual(f1, br'\Flag2')
        self.assertEqual(f1, r'\Flag1')
        self.assertNotEqual(f1, r'\Flag2')
        self.assertNotEqual(f1, f2)

    def test_bytes(self):
        f1 = Flag(br'\testflag')
        self.assertEqual(br'\Testflag', bytes(f1))
        f2 = Flag(b'testflag')
        self.assertEqual(b'testflag', bytes(f2))


class TestStatusAttribute(unittest.TestCase):

    def test_valueerror(self):
        self.assertRaises(ValueError, StatusAttribute, b'TEST')
        self.assertRaises(ValueError, StatusAttribute, b'messages')
        self.assertRaises(ValueError, StatusAttribute, 'MESSAGES')
        StatusAttribute(b'MESSAGES')

    def test_parse(self):
        ret, buf = StatusAttribute.parse(b'  messages  ')
        self.assertEqual(b'MESSAGES', ret.value)
        self.assertEqual(b'  ', buf)

    def test_parse_invalid(self):
        self.assertRaises(InvalidContent, StatusAttribute.parse, b'test')

    def test_bytes(self):
        attr = StatusAttribute(b'MESSAGES')
        self.assertEqual(b'MESSAGES', bytes(attr))


class TestSequenceSet(unittest.TestCase):

    def test_contains(self):
        set1 = SequenceSet([12])
        self.assertTrue(set1.contains(12, 100))
        self.assertFalse(set1.contains(13, 100))
        self.assertFalse(set1.contains(12, 10))
        set2 = SequenceSet(['*'])
        self.assertTrue(set2.contains(21, 100))
        self.assertFalse(set2.contains(21, 20))
        set3 = SequenceSet([(5, 10)])
        self.assertTrue(set3.contains(7, 100))
        self.assertFalse(set3.contains(7, 6))
        self.assertFalse(set3.contains(11, 100))
        self.assertFalse(set3.contains(4, 100))
        set4 = SequenceSet([('*', 10)])
        self.assertTrue(set4.contains(11, 100))
        self.assertFalse(set4.contains(9, 100))
        self.assertFalse(set4.contains(101, 100))
        set5 = SequenceSet([(10, '*')])
        self.assertTrue(set5.contains(11, 100))
        self.assertFalse(set5.contains(9, 100))
        self.assertFalse(set5.contains(101, 100))
        set6 = SequenceSet([('*', '*')])
        self.assertTrue(set6.contains(12, 12))
        self.assertFalse(set6.contains(13, 12))
        self.assertFalse(set6.contains(11, 12))

    def test_parse(self):
        ret, buf = SequenceSet.parse(b'12,*,1:*,*:1  ')
        self.assertEqual([12, '*', (1, '*'), ('*', 1)], ret.sequences)
        self.assertEqual(b'  ', buf)

    def test_parse_error(self):
        self.assertRaises(NotParseable, SequenceSet.parse, b'*,test')
        self.assertRaises(NotParseable, SequenceSet.parse, b'*:test')
        self.assertRaises(NotParseable, SequenceSet.parse, b'')

    def test_bytes(self):
        seq = SequenceSet([12, '*', (1, '*')])
        self.assertEqual(b'12,*,1:*', bytes(seq))
        self.assertEqual(b'12,*,1:*', bytes(seq))


class TestFetchAttribute(unittest.TestCase):

    def test_copy(self):
        attr1 = FetchAttribute(b'TEST1', 'section123', 'partial456')
        attr2 = attr1.copy(b'TEST2')
        self.assertEqual(b'TEST2', attr2.attribute)
        self.assertEqual('section123', attr2.section)
        self.assertEqual('partial456', attr2.partial)

    def test_hash(self):
        attr1 = FetchAttribute(b'TEST')
        attr2 = FetchAttribute(b'TEST')
        self.assertEqual(hash(attr1), hash(attr2))

    def test_parse(self):
        ret, buf = FetchAttribute.parse(
            b'body.peek[1.2.HEADER.FIELDS (A B)]<4.5>  ')
        self.assertEqual(b'BODY.PEEK', ret.attribute)
        self.assertEqual(([1, 2], b'HEADER.FIELDS', {b'A', b'B'}), ret.section)
        self.assertEqual((4, 5), ret.partial)
        self.assertEqual(b'  ', buf)

    def test_parse_simple(self):
        ret1, _ = FetchAttribute.parse(b'ENVELOPE')
        self.assertEqual(b'ENVELOPE', ret1.attribute)
        self.assertIsNone(ret1.section)
        self.assertIsNone(ret1.partial)
        ret2, _ = FetchAttribute.parse(b'BODY')
        self.assertEqual(b'BODY', ret2.attribute)
        self.assertIsNone(ret2.section)
        self.assertIsNone(ret2.partial)

    def test_parse_sections(self):
        ret1, _ = FetchAttribute.parse(b'BODY[1.2]')
        self.assertEqual(b'BODY', ret1.attribute)
        self.assertEqual(([1, 2], None, None), ret1.section)
        self.assertIsNone(ret1.partial)
        ret2, _ = FetchAttribute.parse(b'BODY[1.2.MIME]')
        self.assertEqual(b'BODY', ret2.attribute)
        self.assertEqual(([1, 2], b'MIME', None), ret2.section)
        self.assertIsNone(ret2.partial)
        ret3, _ = FetchAttribute.parse(b'BODY[HEADER]')
        self.assertEqual(b'BODY', ret3.attribute)
        self.assertEqual((None, b'HEADER', None), ret3.section)
        self.assertIsNone(ret3.partial)

    def test_parse_error(self):
        with self.assertRaises(NotParseable):
            FetchAttribute.parse(b'<>')
        with self.assertRaises(NotParseable):
            FetchAttribute.parse(b'BODY[""]')
        with self.assertRaises(NotParseable):
            FetchAttribute.parse(b'BODY[HEADER.FIELDS ()]')
        with self.assertRaises(NotParseable):
            FetchAttribute.parse(b'BODY[TEST]')
        with self.assertRaises(NotParseable):
            FetchAttribute.parse(b'TEST')
        with self.assertRaises(NotParseable):
            FetchAttribute.parse(b'BODY.PEEK')
        with self.assertRaises(NotParseable):
            FetchAttribute.parse(b'BODY[TEXT]<10.0>')

    def test_bytes(self):
        attr1 = FetchAttribute(b'ENVELOPE')
        self.assertEqual(b'ENVELOPE', bytes(attr1))
        self.assertEqual(b'ENVELOPE', bytes(attr1))
        attr2 = FetchAttribute(b'BODY',
                               ([1, 2], b'STUFF', [b'A', b'B']),
                               (b'4', b'5'))
        self.assertEqual(b'BODY[1.2.STUFF (A B)]<4.5>', bytes(attr2))


class TestSearchKey(unittest.TestCase):

    def test_parse(self):
        ret, buf = SearchKey.parse(b'ALL  ')
        self.assertEqual(b'ALL', ret.key)
        self.assertIsNone(ret.filter)
        self.assertFalse(ret.inverse)
        self.assertEqual(b'  ', buf)

    def test_parse_seqset(self):
        ret, buf = SearchKey.parse(b'NOT 1,2,3')
        self.assertIsNone(ret.key)
        self.assertIsInstance(ret.filter, SequenceSet)
        self.assertEqual([1, 2, 3], ret.filter.sequences)
        self.assertTrue(ret.inverse)

    def test_parse_list(self):
        ret, buf = SearchKey.parse(b'(4,5,6 NOT 1,2,3)')
        self.assertIsNone(ret.key)
        self.assertIsInstance(ret.filter, list)
        self.assertEqual(2, len(ret.filter))
        self.assertIsNone(ret.filter[0].key)
        self.assertIsInstance(ret.filter[0].filter, SequenceSet)
        self.assertEqual([4, 5, 6],
                         ret.filter[0].filter.sequences)
        self.assertFalse(ret.filter[0].inverse)
        self.assertIsNone(ret.filter[1].key)
        self.assertIsInstance(ret.filter[1].filter, SequenceSet)
        self.assertEqual([1, 2, 3],
                         ret.filter[1].filter.sequences)
        self.assertTrue(ret.filter[1].inverse)

    def test_parse_list_error(self):
        with self.assertRaises(UnexpectedType):
            SearchKey.parse(b'(TEST)')
        with self.assertRaises(NotParseable):
            SearchKey.parse(b'(1,2,3')

    def test_parse_filter_astring(self):
        ret, buf = SearchKey.parse(b'subject "testing"')
        self.assertEqual(b'SUBJECT', ret.key)
        self.assertEqual('testing', ret.filter)
        self.assertFalse(ret.inverse)

    def test_parse_filter_date(self):
        ret, buf = SearchKey.parse(b'before 01-Jan-1970')
        self.assertEqual(b'BEFORE', ret.key)
        self.assertEqual(datetime(1970, 1, 1), ret.filter)
        self.assertFalse(ret.inverse)

    def test_parse_filter_keyword(self):
        ret, buf = SearchKey.parse(b'keyword test')
        self.assertEqual(b'KEYWORD', ret.key)
        self.assertEqual(Flag(b'test'), ret.filter)
        self.assertFalse(ret.inverse)

    def test_parse_filter_number(self):
        ret, buf = SearchKey.parse(b'larger 1000')
        self.assertEqual(b'LARGER', ret.key)
        self.assertEqual(1000, ret.filter)
        self.assertFalse(ret.inverse)

    def test_parse_filter_uid(self):
        ret, buf = SearchKey.parse(b'UID 1,2,3')
        self.assertEqual(b'UID', ret.key)
        self.assertIsInstance(ret.filter, SequenceSet)
        self.assertEqual([1, 2, 3], ret.filter.sequences)
        self.assertFalse(ret.inverse)

    def test_parse_filter_header(self):
        ret, buf = SearchKey.parse(b'HEADER "From" "test@example.com"')
        self.assertEqual(b'HEADER', ret.key)
        self.assertEqual({'From': 'test@example.com'}, ret.filter)
        self.assertFalse(ret.inverse)

    def test_parse_filter_or(self):
        ret, buf = SearchKey.parse(b'OR NEW OLD')
        self.assertEqual(b'OR', ret.key)
        self.assertEqual(b'NEW', ret.filter[0].key)
        self.assertEqual(b'OLD', ret.filter[1].key)
        self.assertFalse(ret.inverse)

    def test_parse_error(self):
        with self.assertRaises(NotParseable):
            SearchKey.parse(b'test')
        with self.assertRaises(NotParseable):
            SearchKey.parse(b'before stuff')
