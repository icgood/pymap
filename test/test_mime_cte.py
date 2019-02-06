
import unittest

from pymap.mime import MessageContent
from pymap.mime.cte import MessageDecoder

_7bit_body = b"""Testing 7bit\n"""
_8bit_body = b"""Testing\x008bit\x00\n"""
_qp_body = b"""Testing=01Quoted=3DPrintable\n"""
_b64_body = b"""VGVzdGluZwEACkJhc2UgNjQgCg==\n"""


class TestMessageDecoder(unittest.TestCase):

    def test_7bit_cte(self) -> None:
        data = b'\n' + _7bit_body
        msg = MessageContent.parse(data)
        decoded = MessageDecoder.of(msg.header).decode(msg.body)
        self.assertEqual(b'Testing 7bit\n', bytes(decoded))

    def test_8bit_cte(self) -> None:
        data = b'Content-Transfer-Encoding: 8bit\n\n' + _8bit_body
        msg = MessageContent.parse(data)
        decoded = MessageDecoder.of(msg.header).decode(msg.body)
        self.assertEqual(b'Testing\x008bit\x00\n', bytes(decoded))

    def test_quopri_cte(self) -> None:
        data = b'Content-Transfer-Encoding: quoted-printable\n\n' + _qp_body
        msg = MessageContent.parse(data)
        decoded = MessageDecoder.of(msg.header).decode(msg.body)
        self.assertEqual(b'Testing\x01Quoted=Printable\n', bytes(decoded))

    def test_base64_cte(self) -> None:
        data = b'Content-Transfer-Encoding: base64\n\n' + _b64_body
        msg = MessageContent.parse(data)
        decoded = MessageDecoder.of(msg.header).decode(msg.body)
        self.assertEqual(b'Testing\x01\x00\nBase 64 \n', bytes(decoded))
