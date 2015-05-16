
import unittest

from pymap.parsing.response.code import *  # NOQA


class TestAlert(unittest.TestCase):

    def test_bytes(self):
        code = Alert()
        self.assertEqual(b'[ALERT]', bytes(code))


class TestBadCharset(unittest.TestCase):

    def test_bytes(self):
        code = BadCharset()
        self.assertEqual(b'[BADCHARSET]', bytes(code))


class TestCapability(unittest.TestCase):

    def test_bytes(self):
        code = Capability([b'TEST'])
        self.assertEqual(b'[CAPABILITY IMAP4rev1 TEST]', bytes(code))
        code.add(b'STUFF')
        self.assertEqual(b'[CAPABILITY IMAP4rev1 TEST STUFF]', bytes(code))
        code.remove(b'TEST')
        self.assertEqual(b'[CAPABILITY IMAP4rev1 STUFF]', bytes(code))
        code.remove(b'IMAP4rev1')
        self.assertEqual(b'[CAPABILITY IMAP4rev1 STUFF]', bytes(code))

    def test_response(self):
        code = Capability([b'TEST'])
        resp = code.to_response()
        self.assertEqual(b'* CAPABILITY IMAP4rev1 TEST\r\n', bytes(resp))


class TestParse(unittest.TestCase):

    def test_bytes(self):
        code = Parse()
        self.assertEqual(b'[PARSE]', bytes(code))


class TestPermanentFlags(unittest.TestCase):

    def test_bytes(self):
        code = PermanentFlags([br'\One', br'\Two'])
        self.assertEqual(br'[PERMANENTFLAGS (\One \Two)]', bytes(code))


class TestReadOnly(unittest.TestCase):

    def test_bytes(self):
        code = ReadOnly()
        self.assertEqual(b'[READ-ONLY]', bytes(code))


class TestReadWrite(unittest.TestCase):

    def test_bytes(self):
        code = ReadWrite()
        self.assertEqual(b'[READ-WRITE]', bytes(code))


class TestTryCreate(unittest.TestCase):

    def test_bytes(self):
        code = TryCreate()
        self.assertEqual(b'[TRYCREATE]', bytes(code))


class TestUidNext(unittest.TestCase):

    def test_bytes(self):
        code = UidNext(13)
        self.assertEqual(b'[UIDNEXT 13]', bytes(code))


class TestUidValidity(unittest.TestCase):

    def test_bytes(self):
        code = UidValidity(1234)
        self.assertEqual(b'[UIDVALIDITY 1234]', bytes(code))


class TestUnseen(unittest.TestCase):

    def test_bytes(self):
        code = Unseen(3)
        self.assertEqual(b'[UNSEEN 3]', bytes(code))
