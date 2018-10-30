
import unittest

from pymap.parsing.response.code import Alert, Capability, Parse, \
    PermanentFlags, ReadOnly, ReadWrite, TryCreate, UidNext, UidValidity, \
    Unseen, AppendUid, CopyUid


class TestAlert(unittest.TestCase):

    def test_bytes(self):
        code = Alert()
        self.assertEqual(b'[ALERT]', bytes(code))


class TestCapability(unittest.TestCase):

    def test_bytes(self):
        code = Capability([])
        self.assertEqual(b'[CAPABILITY IMAP4rev1]', bytes(code))
        code = Capability([b'TEST'])
        self.assertEqual(b'[CAPABILITY IMAP4rev1 TEST]', bytes(code))
        code = Capability([b'TEST', b'STUFF'])
        self.assertEqual(b'[CAPABILITY IMAP4rev1 TEST STUFF]', bytes(code))


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


class TestAppendUid(unittest.TestCase):

    def test_bytes(self):
        code = AppendUid(12345, [1, 2, 3, 5])
        self.assertEqual(b'[APPENDUID 12345 1:3,5]', bytes(code))


class TestCopyUid(unittest.TestCase):

    def test_bytes(self):
        code = CopyUid(12345, [(1, 100), (2, 101), (3, 102), (5, 103)])
        self.assertEqual(b'[COPYUID 12345 1:3,5 100:103]', bytes(code))
