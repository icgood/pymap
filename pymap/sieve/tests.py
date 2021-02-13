
from __future__ import annotations

import re
from abc import abstractmethod, ABCMeta
from collections.abc import Sequence
from email.headerregistry import Address, AddressHeader
from re import Pattern

from pymap.mime import MessageContent
from pymap.parsing.message import AppendMessage
from sievelib.commands import Command

from .util import AddressPart, MatchType, SizeComparator, str_list

__all__ = ['SieveTest']


class SieveTest(metaclass=ABCMeta):
    """Base class for all sieve tests.

    See Also:
        `RFC 5228 5. <https://tools.ietf.org/html/rfc5228#section-5>`_

    """

    @classmethod
    def of(cls, cmd: Command) -> SieveTest:
        """Given a test command, determine the implementation sub-class and
        return an instance.

        Args:
            cmd: The test command.

        """
        if cmd.name == 'allof':
            return AllOfTest([SieveTest.of(test)
                              for test in cmd.arguments['tests']])
        elif cmd.name == 'anyof':
            return AnyOfTest([SieveTest.of(test)
                              for test in cmd.arguments['tests']])
        elif cmd.name == 'not':
            return NotTest(SieveTest.of(cmd.arguments['test']))
        elif cmd.name == 'true':
            return TrueTest()
        elif cmd.name == 'false':
            return FalseTest()
        elif cmd.name in ('address', 'envelope'):
            address_part = AddressPart.of(cmd.arguments.get('address-part'))
            match_type = MatchType.of(cmd.arguments.get('match-type'))
            case_sensitive = cmd.arguments.get('comparator') == '"i;octet"'
            header_list = str_list(cmd.arguments['header-list'])
            key_list = str_list(cmd.arguments['key-list'])
            if cmd.name == 'address':
                return AddressTest(header_list, key_list, address_part,
                                   match_type, case_sensitive)
            else:
                return EnvelopeTest(header_list, key_list, address_part,
                                    match_type, case_sensitive)
        elif cmd.name == 'exists':
            header_names = str_list(cmd.arguments['header-names'])
            return ExistsTest(header_names)
        elif cmd.name == 'header':
            match_type = MatchType.of(cmd.arguments.get('match-type'))
            case_sensitive = cmd.arguments.get('comparator') == '"i;octet"'
            header_names = str_list(cmd.arguments['header-names'])
            key_list = str_list(cmd.arguments['key-list'])
            return HeaderTest(header_names, key_list, match_type,
                              case_sensitive)
        elif cmd.name == 'size':
            comparator = SizeComparator.of(cmd.arguments['comparator'])
            limit = int(cmd.arguments['limit'])
            return SizeTest(comparator, limit)
        else:
            raise NotImplementedError(cmd.name)

    @abstractmethod
    def run(self, sender: str, recipient: str, append_msg: AppendMessage,
            content: MessageContent) -> bool:
        """Run the test implementation on the appended message data, returning
        True if the test matched the data. Must be overridden by sub-classes.

        Args:
            sender: The envelope sender of the message.
            recipient: The envelope recipient of the message.
            append_msg: The message to be appended.
            content: The parsed message content.

        """
        ...


class AllOfTest(SieveTest):

    def __init__(self, tests: Sequence[SieveTest]) -> None:
        super().__init__()
        self._tests = tests

    def run(self, sender: str, recipient: str, append_msg: AppendMessage,
            content: MessageContent) -> bool:
        return all(test.run(sender, recipient, append_msg, content)
                   for test in self._tests)


class AnyOfTest(SieveTest):

    def __init__(self, tests: Sequence[SieveTest]) -> None:
        super().__init__()
        self._tests = tests

    def run(self, sender: str, recipient: str, append_msg: AppendMessage,
            content: MessageContent) -> bool:
        return any(test.run(sender, recipient, append_msg, content)
                   for test in self._tests)


class NotTest(SieveTest):

    def __init__(self, test: SieveTest) -> None:
        super().__init__()
        self._test = test

    def run(self, sender: str, recipient: str, append_msg: AppendMessage,
            content: MessageContent) -> bool:
        return not self._test.run(sender, recipient, append_msg, content)


class TrueTest(SieveTest):

    def run(self, sender: str, recipient: str, append_msg: AppendMessage,
            content: MessageContent) -> bool:
        return True


class FalseTest(SieveTest):

    def run(self, sender: str, recipient: str, append_msg: AppendMessage,
            content: MessageContent) -> bool:
        return False


class MatchTest(SieveTest):

    _wildcards = re.compile(r'([\*\?])')

    @classmethod
    def _compile(cls, key_list: Sequence[str], match_type: MatchType,
                 case_sensitive: bool) -> Sequence[Pattern]:
        flags = 0 if case_sensitive else re.I
        ret: list[Pattern] = []
        for key in key_list:
            if match_type == MatchType.MATCHES:
                pattern_parts: list[str] = []
                for part in cls._wildcards.split(key):
                    if part == '*':
                        pattern_parts.append('.*?')
                    elif part == '?':
                        pattern_parts.append('.')
                    else:
                        pattern_parts.append(re.escape(part))
                pattern = ''.join(pattern_parts)
            else:
                pattern = re.escape(key)
            if match_type in (MatchType.IS, MatchType.MATCHES):
                pattern = '^' + pattern + '$'
            ret.append(re.compile(pattern, flags))
        return ret


class AddressTest(MatchTest):

    def __init__(self, header_list: Sequence[str], key_list: Sequence[str],
                 address_part: AddressPart, match_type: MatchType,
                 case_sensitive: bool) -> None:
        super().__init__()
        self._header_set = {hdr.encode('ascii') for hdr in header_list}
        self._address_part = address_part
        self._patterns = self._compile(key_list, match_type, case_sensitive)

    def run(self, sender: str, recipient: str, append_msg: AppendMessage,
            content: MessageContent) -> bool:
        part = self._address_part
        for name in self._header_set:
            values = content.header.parsed.get(name, [])
            for value in values:
                if isinstance(value, AddressHeader):
                    for address in value.addresses:
                        if part == AddressPart.LOCALPART:
                            addr_part = address.username
                        elif part == AddressPart.DOMAIN:
                            addr_part = address.domain
                        else:
                            addr_part = address.addr_spec
                        for pattern in self._patterns:
                            if pattern.match(addr_part) is not None:
                                return True
        return False


class EnvelopeTest(AddressTest):

    def _check_address(self, envelope_part: bytes, address: str) -> bool:
        if envelope_part not in self._header_set:
            return False
        try:
            addr_obj = Address(addr_spec=address)
        except Exception:
            addr_obj = Address(username=address)
        part = self._address_part
        if part == AddressPart.LOCALPART:
            addr_part = addr_obj.username
        elif part == AddressPart.DOMAIN:
            addr_part = addr_obj.domain
        else:
            addr_part = addr_obj.addr_spec
            if addr_part == '<>':
                addr_part = ''
        for pattern in self._patterns:
            if pattern.match(addr_part) is not None:
                return True
        return False

    def run(self, sender: str, recipient: str, append_msg: AppendMessage,
            content: MessageContent) -> bool:
        if self._check_address(b'from', sender):
            return True
        elif self._check_address(b'to', recipient):
            return True
        else:
            return False


class ExistsTest(SieveTest):

    def __init__(self, header_names: Sequence[str]) -> None:
        super().__init__()
        self._header_names = {hdr.encode('ascii') for hdr in header_names}

    def run(self, sender: str, recipient: str, append_msg: AppendMessage,
            content: MessageContent) -> bool:
        return all(name in content.header.parsed
                   for name in self._header_names)


class HeaderTest(MatchTest):

    def __init__(self, header_names: Sequence[str], key_list: Sequence[str],
                 match_type: MatchType, case_sensitive: bool) -> None:
        super().__init__()
        self._header_names = [hdr.encode('ascii') for hdr in header_names]
        self._patterns = self._compile(key_list, match_type, case_sensitive)

    def run(self, sender: str, recipient: str, append_msg: AppendMessage,
            content: MessageContent) -> bool:
        for name in self._header_names:
            values = content.header.parsed.get(name, [])
            for value in values:
                value_str = str(value)
                for pattern in self._patterns:
                    if pattern.match(value_str) is not None:
                        return True
        return False


class SizeTest(SieveTest):

    def __init__(self, comparator: SizeComparator, limit: int) -> None:
        super().__init__()
        self._comparator = comparator
        self._limit = limit

    def run(self, sender: str, recipient: str, append_msg: AppendMessage,
            content: MessageContent) -> bool:
        length = len(content)
        if self._comparator == SizeComparator.OVER:
            return length > self._limit
        else:
            return length < self._limit
