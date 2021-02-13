
from __future__ import annotations

import enum
from collections.abc import Mapping, Sequence
from typing import Optional

from pymap.bytes import BytesFormat, MaybeBytes, WriteStream, Writeable
from pymap.parsing.exceptions import NotParseable
from pymap.parsing.primitives import String, QuotedString, LiteralString

__all__ = ['Condition', 'Response', 'BadCommandResponse',
           'CapabilitiesResponse', 'GetScriptResponse', 'ListScriptsResponse']

_Capabilities = Mapping[bytes, Optional[MaybeBytes]]


class Condition(enum.Enum):
    OK = enum.auto()
    NO = enum.auto()
    BYE = enum.auto()

    def __bytes__(self) -> bytes:
        return bytes(str(self.name), 'ascii')


class Response(Writeable):

    def __init__(self, condition: Condition, *, code: MaybeBytes = None,
                 text: str = None) -> None:
        super().__init__()
        self.condition = condition
        self.code = code
        self.text = text
        self._raw: Optional[bytes] = None

    @property
    def is_bye(self) -> bool:
        return self.condition == Condition.BYE

    def write(self, writer: WriteStream) -> None:
        writer.write(bytes(self.condition))
        if self.code is not None:
            writer.write(b' (%b)' % bytes(self.code))
        if self.text is not None:
            text_bytes = self.text.rstrip('\r\n').encode('utf-8', 'replace')
            text_str = String.build(text_bytes)
            writer.write(b' ')
            text_str.write(writer)
        writer.write(b'\r\n')

    def __bytes__(self) -> bytes:
        if self._raw is None:
            self._raw = self.tobytes()
        return self._raw

    def __repr__(self) -> str:
        raw = bytes(self).decode('utf-8')
        return f'<Response {repr(raw)}>'


class BadCommandResponse(Response):

    def __init__(self, exc: NotParseable) -> None:
        super().__init__(Condition.NO, text='Bad command: %s' % exc)


class NoOpResponse(Response):

    def __init__(self, tag: Optional[bytes]) -> None:
        if tag is None:
            code: Optional[bytes] = None
        else:
            code = BytesFormat(b'TAG %b') % String.build(tag)
        super().__init__(Condition.OK, code=code)


class CapabilitiesResponse(Response):

    def __init__(self, capabilities: _Capabilities, *,
                 code: MaybeBytes = None) -> None:
        super().__init__(Condition.OK, code=code)
        self.capabilities = capabilities

    def write(self, writer: WriteStream) -> None:
        for cap_name, cap_val in self.capabilities.items():
            quoted_name = QuotedString(cap_name)
            if cap_val is None:
                line = BytesFormat(b'%b\r\n') % (quoted_name, )
            else:
                quoted_val = QuotedString(bytes(cap_val))
                line = BytesFormat(b'%b %b\r\n') % (quoted_name, quoted_val)
            writer.write(line)
        super().write(writer)


class GetScriptResponse(Response):

    def __init__(self, script_data: bytes) -> None:
        super().__init__(Condition.OK)
        self.script_data = script_data

    def write(self, writer: WriteStream) -> None:
        data_str = LiteralString(self.script_data)
        data_str.write(writer)
        writer.write(b'\r\n')
        super().write(writer)


class ListScriptsResponse(Response):

    def __init__(self, active: Optional[str], names: Sequence[str]) -> None:
        super().__init__(Condition.OK)
        self.active = active
        self.names = names

    def write(self, writer: WriteStream) -> None:
        for name in self.names:
            name_str = String.build(name)
            name_str.write(writer)
            if self.active and name == self.active:
                writer.write(b' ACTIVE\r\n')
            else:
                writer.write(b'\r\n')
        super().write(writer)
