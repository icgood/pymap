
import json
import unittest

from pymap.mime import MessageContent


class TestMessageContents(unittest.TestCase):

    def test_parse(self) -> None:
        header = b'from: sender@example.com \n' \
                 b'to: user1@example.com,\n' \
                 b' user2@example.com\n' \
                 b'to:  user3@example.com\r\n' \
                 b'subject: hello world \xff\r\n' \
                 b'test:\n' \
                 b' more stuff\n' \
                 b'\n'
        body = b'abc\n'
        raw = header + body
        msg_parsed = MessageContent.parse(raw)
        json_obj = json.loads(json.dumps(msg_parsed.json))
        msg_json = MessageContent.from_json(raw, json_obj)
        for msg in (msg_parsed, msg_json):
            self.assertEqual(raw, bytes(msg))
            self.assertEqual(9, msg.lines)
            self.assertEqual(header, bytes(msg.header))
            self.assertEqual({b'from': ['sender@example.com'],
                              b'to': ['user1@example.com, user2@example.com',
                                      'user3@example.com'],
                              b'subject': ['hello world \ufffd'],
                              b'test': [' more stuff']}, msg.header.parsed)
            self.assertEqual('hello world \ufffd', msg.header.parsed.subject)
            self.assertEqual(body, bytes(msg.body))
            self.assertFalse(msg.body.has_nested)

    def test_parse_rfc822(self) -> None:
        header = b'subject: rfc822 test\n' \
                 b'content-type: message/rfc822\n' \
                 b'\n'
        sub_header = b'content-type: text/html\n' \
                     b'\n'
        sub_body = b'<html><body><h1>part two</h1></body></html>\n'
        body = sub_header + sub_body
        raw = header + body
        msg_parsed = MessageContent.parse(raw)
        json_obj = json.loads(json.dumps(msg_parsed.json))
        msg_json = MessageContent.from_json(raw, json_obj)
        for msg in (msg_parsed, msg_json):
            self.assertEqual(raw, bytes(msg))
            self.assertEqual(6, msg.lines)
            self.assertEqual(header, bytes(msg.header))
            self.assertEqual({b'subject': ['rfc822 test'],
                              b'content-type': ['message/rfc822']},
                             msg.header.parsed)
            self.assertEqual(body, bytes(msg.body))
            self.assertTrue(msg.body.has_nested)
            self.assertEqual(1, len(msg.body.nested))
            self.assertEqual(body, bytes(msg.body.nested[0]))
            self.assertEqual(sub_header, bytes(msg.body.nested[0].header))
            self.assertEqual(sub_body, bytes(msg.body.nested[0].body))
            self.assertEqual({b'content-type': ['text/html']},
                             msg.body.nested[0].header.parsed)

    def test_parse_multipart(self) -> None:
        header = b'subject: multipart test\n' \
                 b'content-type: multipart/mixed;\n' \
                 b' boundary="testbound"\n' \
                 b'\n'
        part1 = b'\n' \
                b'part one!\n' \
                b'\n' \
                b'lorem ipsum etc.\n'
        part2 = b'content-type: text/html\n' \
                b'\n' \
                b'<html><body><h1>part two</h1></body></html>\n'
        body = b'preamble\n' \
               b'--testbound\n' + part1 + \
               b'--testbound\n' + part2 + \
               b'--testbound--\n' \
               b'epilogue\n'
        raw = header + body
        msg_parsed = MessageContent.parse(raw)
        json_obj = json.loads(json.dumps(msg_parsed.json))
        msg_json = MessageContent.from_json(raw, json_obj)
        for msg in (msg_parsed, msg_json):
            self.assertEqual(raw, bytes(msg))
            self.assertEqual(16, msg.lines)
            self.assertEqual(header, bytes(msg.header))
            self.assertEqual({b'subject': ['multipart test'],
                              b'content-type': ['multipart/mixed; '
                                                'boundary="testbound"']},
                             msg.header.parsed)
            self.assertEqual(body, bytes(msg.body))
            self.assertTrue(msg.body.has_nested)
            self.assertEqual(2, len(msg.body.nested))
            self.assertEqual(part1, bytes(msg.body.nested[0]))
            self.assertEqual({}, msg.body.nested[0].header.parsed)
            self.assertEqual(part2, bytes(msg.body.nested[1]))
            self.assertEqual({b'content-type': ['text/html']},
                             msg.body.nested[1].header.parsed)
