
import unittest

from pymap.parsing.command import BadCommand
from pymap.parsing.command.any import NoOpCommand
from pymap.parsing.response import Response, ResponseContinuation, \
    ResponseBad, ResponseBadCommand, ResponseNo, ResponseOk, ResponseBye


class TestResponse(unittest.TestCase):

    def test_bytes(self):
        resp = Response(b'tag', b'response test')
        self.assertEqual(b'tag response test\r\n', bytes(resp))
        self.assertEqual(b'tag response test\r\n', bytes(resp))
        resp.add_untagged(b'test data 1\r\n')
        self.assertEqual(b'test data 1\r\ntag response test\r\n', bytes(resp))
        resp.add_untagged(b'test data 2\r\n')
        self.assertEqual(b'test data 1\r\ntest data 2\r\n'
                         b'tag response test\r\n', bytes(resp))


class TestResponseContinuation(unittest.TestCase):

    def test_bytes(self):
        resp = ResponseContinuation(b'test continuation')
        self.assertEqual(b'+ test continuation\r\n', bytes(resp))


class TestResponseBad(unittest.TestCase):

    def test_bytes(self):
        resp1 = ResponseBad(b'tag', b'bad response')
        self.assertEqual(b'tag BAD bad response\r\n', bytes(resp1))
        resp2 = ResponseBad(b'tag', b'bad response', b'STUFF')
        self.assertEqual(b'tag BAD STUFF bad response\r\n', bytes(resp2))


class TestResponseBadCommand(unittest.TestCase):

    def test_bytes(self):
        cmd = BadCommand(b'bad', b'tag', NoOpCommand)
        resp = ResponseBadCommand(cmd)
        self.assertEqual(b'tag BAD NOOP: [:ERROR:]bad\r\n', bytes(resp))


class TestResponseNo(unittest.TestCase):

    def test_bytes(self):
        resp1 = ResponseNo(b'tag', b'invalid response')
        self.assertEqual(b'tag NO invalid response\r\n', bytes(resp1))
        resp2 = ResponseNo(b'tag', b'invalid response', b'STUFF')
        self.assertEqual(b'tag NO STUFF invalid response\r\n', bytes(resp2))


class TestResponseOk(unittest.TestCase):

    def test_bytes(self):
        resp1 = ResponseOk(b'tag', b'ok response')
        self.assertEqual(b'tag OK ok response\r\n', bytes(resp1))
        resp2 = ResponseOk(b'tag', b'ok response', b'STUFF')
        self.assertEqual(b'tag OK STUFF ok response\r\n', bytes(resp2))


class TestResponseBye(unittest.TestCase):

    def test_bytes(self):
        resp = ResponseBye(b'bye response')
        self.assertEqual(b'* BYE bye response\r\n', bytes(resp))
