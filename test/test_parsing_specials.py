
import unittest
from datetime import datetime, timezone, timedelta

from pymap.parsing import Params, NotParseable, UnexpectedType, InvalidContent
from pymap.parsing.specials import AString, Tag, Mailbox, DateTime, Flag, \
    StatusAttribute, SequenceSet, FetchAttribute, SearchKey


class TestAString(unittest.TestCase):

    def test_parse(self):
        ret, buf = AString.parse(b'  a001[+]  ', Params())
        self.assertIsInstance(ret, AString)
        self.assertEqual(b'a001[+]', ret.value)
        self.assertEqual(b'  ', buf)

    def test_parse_quoted(self):
        ret, buf = AString.parse(br'  "a bc \" d"  ', Params())
        self.assertIsInstance(ret, AString)
        self.assertEqual(b'a bc " d', ret.value)
        self.assertEqual(b'  ', buf)

    def test_parse_literal(self):
        ret, buf = AString.parse(
            b'  {4}\r\n', Params(continuations=[b'abcd  ']))
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
        ret, buf = Tag.parse(b' a[001]  ', Params())
        self.assertIsInstance(ret, Tag)
        self.assertEqual(b'a[001]', ret.value)
        self.assertEqual(b'  ', buf)

    def test_parse_failure(self):
        with self.assertRaises(NotParseable):
            Tag.parse(b'', Params())

    def test_bytes(self):
        tag1 = Tag(b'a[001]')
        self.assertEqual(b'a[001]', bytes(tag1))


class TestMailbox(unittest.TestCase):

    def test_parse(self):
        ret, buf = Mailbox.parse(
            b'~peter/mail/&-/&U,BTFw-/&ZeVnLIqe-', Params())
        self.assertIsInstance(ret, Mailbox)
        self.assertEqual('~peter/mail/&/台北/日本語', ret.value)
        self.assertEqual(b'', buf)

    def test_parse_inbox(self):
        ret, buf = Mailbox.parse(b'  iNbOx  ', Params())
        self.assertIsInstance(ret, Mailbox)
        self.assertEqual('INBOX', ret.value)
        self.assertEqual(b'  ', buf)

    def test_parse_quoted(self):
        ret, buf = Mailbox.parse(b'  "test mailbox \\"stuff\\""  ', Params())
        self.assertIsInstance(ret, Mailbox)
        self.assertEqual('test mailbox "stuff"', ret.value)
        self.assertEqual(b'  ', buf)

    def test_parse_failure(self):
        with self.assertRaises(NotParseable):
            Mailbox.parse(b'  ', Params())

    def test_bytes(self):
        mbx = Mailbox('~peter/mail/&/台北/日本語')
        self.assertEqual(b'~peter/mail/&-/&U,BTFw-/&ZeVnLIqe-', bytes(mbx))
        self.assertEqual(b'~peter/mail/&-/&U,BTFw-/&ZeVnLIqe-', bytes(mbx))

    def test_str(self):
        mbx = Mailbox('~peter/mail/&/台北/日本語')
        self.assertEqual('~peter/mail/&/台北/日本語', str(mbx))


class TestDateTime(unittest.TestCase):

    def test_parse(self):
        ret, buf = DateTime.parse(b'"1-Jan-2000 01:02:03 +0500"', Params())
        self.assertIsInstance(ret, DateTime)
        self.assertEqual(1, ret.value.day)
        self.assertEqual(1, ret.value.month)
        self.assertEqual(2000, ret.value.year)
        self.assertEqual(1, ret.value.hour)
        self.assertEqual(2, ret.value.minute)
        self.assertEqual(3, ret.value.second)
        self.assertEqual(18000.0, ret.value.utcoffset().total_seconds())

    def test_parse_failure(self):
        with self.assertRaises(InvalidContent):
            DateTime.parse(b'"test"', Params())

    def test_bytes(self):
        dt1 = DateTime(datetime(2000, 1, 1, 1, 2, 3,
                                tzinfo=timezone(timedelta(hours=5))))
        self.assertEqual(b'"01-Jan-2000 01:02:03 +0500"', bytes(dt1))
        dt2 = DateTime(datetime.now(), b'testing')
        self.assertEqual(b'"testing"', bytes(dt2))


class TestFlag(unittest.TestCase):

    def test_parse(self):
        ret1, buf1 = Flag.parse(br'MyFlag  \Seen  ', Params())
        self.assertEqual(b'MyFlag', ret1.value)
        self.assertEqual(br'  \Seen  ', buf1)
        ret2, buf2 = Flag.parse(buf1, Params())
        self.assertEqual(br'\Seen', ret2.value)
        self.assertEqual(b'  ', buf2)

    def test_bytes(self):
        f1 = Flag(br'\testflag')
        self.assertEqual(br'\Testflag', bytes(f1))
        f2 = Flag(b'testflag')
        self.assertEqual(b'testflag', bytes(f2))


class TestStatusAttribute(unittest.TestCase):

    def test_valueerror(self):
        with self.assertRaises(ValueError):
            StatusAttribute(b'TEST')
        with self.assertRaises(ValueError):
            StatusAttribute(b'messages')
        StatusAttribute(b'MESSAGES')

    def test_parse(self):
        ret, buf = StatusAttribute.parse(b'  messages  ', Params())
        self.assertEqual(b'MESSAGES', ret.value)
        self.assertEqual(b'  ', buf)

    def test_parse_invalid(self):
        with self.assertRaises(InvalidContent):
            StatusAttribute.parse(b'test', Params())

    def test_bytes(self):
        attr = StatusAttribute(b'MESSAGES')
        self.assertEqual(b'MESSAGES', bytes(attr))


class TestSequenceSet(unittest.TestCase):

    def test_parse(self):
        ret, buf = SequenceSet.parse(b'12,*,1:*,*:1  ', Params())
        self.assertEqual([12, '*', (1, '*'), ('*', 1)], ret.value)
        self.assertEqual(b'  ', buf)

    def test_parse_error(self):
        with self.assertRaises(NotParseable):
            SequenceSet.parse(b'*,test', Params())
        with self.assertRaises(NotParseable):
            SequenceSet.parse(b'*:test', Params())
        with self.assertRaises(NotParseable):
            SequenceSet.parse(b'', Params())


class TestFetchAttribute(unittest.TestCase):

    def test_hash(self):
        attr1 = FetchAttribute(b'TEST')
        attr2 = FetchAttribute(b'TEST')
        self.assertEqual(hash(attr1), hash(attr2))

    def test_parse(self):
        ret, buf = FetchAttribute.parse(
            b'body.peek[1.2.HEADER.FIELDS (A B)]<4.5>  ', Params())
        self.assertEqual(b'BODY.PEEK', ret.value)
        self.assertEqual({1, 2}, ret.section.parts)
        self.assertEqual(b'HEADER.FIELDS', ret.section.msgtext)
        self.assertEqual({b'A', b'B'}, ret.section.headers)
        self.assertEqual((4, 5), ret.partial)
        self.assertEqual(b'  ', buf)

    def test_parse_simple(self):
        ret1, _ = FetchAttribute.parse(b'ENVELOPE', Params())
        self.assertEqual(b'ENVELOPE', ret1.value)
        self.assertIsNone(ret1.section)
        self.assertIsNone(ret1.partial)
        ret2, _ = FetchAttribute.parse(b'BODY', Params())
        self.assertEqual(b'BODY', ret2.value)
        self.assertIsNone(ret2.section)
        self.assertIsNone(ret2.partial)

    def test_parse_sections(self):
        ret1, _ = FetchAttribute.parse(b'BODY[1.2]', Params())
        self.assertEqual(b'BODY', ret1.value)
        self.assertEqual({1, 2}, ret1.section.parts)
        self.assertIsNone(ret1.section.msgtext)
        self.assertIsNone(ret1.section.headers)
        self.assertIsNone(ret1.partial)
        ret2, _ = FetchAttribute.parse(b'BODY[1.2.MIME]', Params())
        self.assertEqual(b'BODY', ret2.value)
        self.assertEqual({1, 2}, ret2.section.parts)
        self.assertEqual(b'MIME', ret2.section.msgtext)
        self.assertIsNone(ret2.section.headers)
        self.assertIsNone(ret2.partial)
        ret3, _ = FetchAttribute.parse(b'BODY[HEADER]', Params())
        self.assertEqual(b'BODY', ret3.value)
        self.assertIsNone(ret3.section.parts)
        self.assertEqual(b'HEADER', ret3.section.msgtext)
        self.assertIsNone(ret3.section.headers)
        self.assertIsNone(ret3.partial)

    def test_parse_error(self):
        with self.assertRaises(NotParseable):
            FetchAttribute.parse(b'<>', Params())
        with self.assertRaises(NotParseable):
            FetchAttribute.parse(b'BODY[""]', Params())
        with self.assertRaises(NotParseable):
            FetchAttribute.parse(b'BODY[HEADER.FIELDS ()]', Params())
        with self.assertRaises(NotParseable):
            FetchAttribute.parse(b'BODY[TEST]', Params())
        with self.assertRaises(NotParseable):
            FetchAttribute.parse(b'TEST', Params())
        with self.assertRaises(NotParseable):
            FetchAttribute.parse(b'BODY.PEEK', Params())
        with self.assertRaises(NotParseable):
            FetchAttribute.parse(b'BODY[TEXT]<10.0>', Params())

    def test_bytes(self):
        attr1 = FetchAttribute(b'ENVELOPE')
        self.assertEqual(b'ENVELOPE', bytes(attr1))
        self.assertEqual(b'ENVELOPE', bytes(attr1))
        section = FetchAttribute.Section((1, 2), b'STUFF', [b'A', b'B'])
        attr2 = FetchAttribute(b'BODY', section, (4, 5))
        self.assertEqual(b'BODY[1.2.STUFF (A B)]<4.5>', bytes(attr2))
        self.assertEqual(b'BODY[1.2.STUFF (A B)]<4>',
                         bytes(attr2.for_response))


class TestSearchKey(unittest.TestCase):

    def test_parse(self):
        ret, buf = SearchKey.parse(b'ALL  ', Params())
        self.assertEqual(b'ALL', ret.value)
        self.assertIsNone(ret.filter)
        self.assertFalse(ret.inverse)
        self.assertEqual(b'  ', buf)

    def test_parse_seqset(self):
        ret, buf = SearchKey.parse(b'NOT 1,2,3', Params())
        self.assertEqual(b'SEQSET', ret.value)
        self.assertIsInstance(ret.filter, SequenceSet)
        self.assertEqual([1, 2, 3], ret.filter.value)
        self.assertTrue(ret.inverse)

    def test_parse_list(self):
        ret, buf = SearchKey.parse(b'(4,5,6 NOT 1,2,3)', Params())
        self.assertEqual(b'KEYSET', ret.value)
        self.assertIsInstance(ret.filter, list)
        self.assertEqual(2, len(ret.filter))
        self.assertEqual(b'SEQSET', ret.filter[0].value)
        self.assertIsInstance(ret.filter[0].filter, SequenceSet)
        self.assertEqual([4, 5, 6],
                         ret.filter[0].filter.value)
        self.assertFalse(ret.filter[0].inverse)
        self.assertEqual(b'SEQSET', ret.filter[1].value)
        self.assertIsInstance(ret.filter[1].filter, SequenceSet)
        self.assertEqual([1, 2, 3],
                         ret.filter[1].filter.value)
        self.assertTrue(ret.filter[1].inverse)

    def test_parse_list_error(self):
        with self.assertRaises(UnexpectedType):
            SearchKey.parse(b'(TEST)', Params())
        with self.assertRaises(NotParseable):
            SearchKey.parse(b'(1,2,3', Params())

    def test_parse_filter_astring(self):
        ret, buf = SearchKey.parse(b'subject "testing"', Params())
        self.assertEqual(b'SUBJECT', ret.value)
        self.assertEqual('testing', ret.filter)
        self.assertFalse(ret.inverse)

    def test_parse_filter_date(self):
        ret, buf = SearchKey.parse(b'before 01-Jan-1970', Params())
        self.assertEqual(b'BEFORE', ret.value)
        self.assertEqual(datetime(1970, 1, 1), ret.filter)
        self.assertFalse(ret.inverse)

    def test_parse_filter_keyword(self):
        ret, buf = SearchKey.parse(b'keyword test', Params())
        self.assertEqual(b'KEYWORD', ret.value)
        self.assertEqual(b'test', ret.filter)
        self.assertFalse(ret.inverse)

    def test_parse_filter_number(self):
        ret, buf = SearchKey.parse(b'larger 1000', Params())
        self.assertEqual(b'LARGER', ret.value)
        self.assertEqual(1000, ret.filter)
        self.assertFalse(ret.inverse)

    def test_parse_filter_uid(self):
        ret, buf = SearchKey.parse(b'UID 1,2,3', Params())
        self.assertEqual(b'SEQSET', ret.value)
        self.assertIsInstance(ret.filter, SequenceSet)
        self.assertEqual([1, 2, 3], ret.filter.value)
        self.assertFalse(ret.inverse)

    def test_parse_filter_header(self):
        ret, buf = SearchKey.parse(
            b'HEADER "From" "test@example.com"', Params())
        self.assertEqual(b'HEADER', ret.value)
        self.assertEqual(('From', 'test@example.com'), ret.filter)
        self.assertFalse(ret.inverse)

    def test_parse_filter_or(self):
        ret, buf = SearchKey.parse(b'OR NEW OLD', Params())
        self.assertEqual(b'OR', ret.value)
        self.assertEqual(b'NEW', ret.filter[0].value)
        self.assertEqual(b'OLD', ret.filter[1].value)
        self.assertFalse(ret.inverse)

    def test_parse_error(self):
        with self.assertRaises(NotParseable):
            SearchKey.parse(b'test', Params())
        with self.assertRaises(NotParseable):
            SearchKey.parse(b'before stuff', Params())
