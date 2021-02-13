
from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Optional

from . import AString, SequenceSet
from .. import Params, Parseable
from ..exceptions import NotParseable
from ..primitives import Number, List
from ...bytes import BytesFormat, rev

__all__ = ['ExtensionOption', 'ExtensionOptions']


class ExtensionOption(Parseable[bytes]):
    """Represents a single command option, which may or may not have an
    associated value.

    See Also:
        `RFC 4466 2.1. <https://tools.ietf.org/html/rfc4466#section-2.1>`_

    Args:
        option: The name of the option.
        arg: The option argument, if any.

    """

    _opt_pattern = rev.compile(br'[a-zA-Z_.-][a-zA-Z0-9_.:-]*')

    def __init__(self, option: bytes, arg: List) -> None:
        super().__init__()
        self.option = option
        self.arg = arg
        self._raw_arg: Optional[bytes] = None

    @property
    def value(self) -> bytes:
        return self.option

    def __bytes__(self) -> bytes:
        if self.arg.value:
            return BytesFormat(b'%b %b') % (self.option, self.raw_arg)
        else:
            return self.option

    @property
    def raw_arg(self) -> bytes:
        if self._raw_arg is None:
            if not self.arg:
                self._raw_arg = b''
            elif len(self.arg) == 1:
                arg_0 = self.arg.value[0]
                if isinstance(arg_0, (Number, SequenceSet)):
                    self._raw_arg = bytes(arg_0)
                else:
                    self._raw_arg = bytes(self.arg)
            else:
                self._raw_arg = bytes(self.arg)
        return self._raw_arg

    @classmethod
    def _parse_arg(cls, buf: memoryview, params: Params) \
            -> tuple[List, memoryview]:
        try:
            num, buf = Number.parse(buf, params)
        except NotParseable:
            pass
        else:
            arg = List([num])
            return arg, buf
        try:
            seq_set, buf = SequenceSet.parse(buf, params)
        except NotParseable:
            pass
        else:
            arg = List([seq_set])
            return arg, buf
        try:
            params_copy = params.copy(list_expected=[AString, List])
            return List.parse(buf, params_copy)
        except NotParseable:
            pass
        return List([]), buf

    @classmethod
    def parse(cls, buf: memoryview, params: Params) \
            -> tuple[ExtensionOption, memoryview]:
        start = cls._whitespace_length(buf)
        match = cls._opt_pattern.match(buf, start)
        if not match:
            raise NotParseable(buf[start:])
        option = match.group(0).upper()
        buf = buf[match.end(0):]
        arg, buf = cls._parse_arg(buf, params)
        return cls(option, arg), buf


class ExtensionOptions(Parseable[Mapping[bytes, List]]):
    """Represents a set of command options, which may or may not have an
    associated argument. Command options are always optional, so the parsing
    will not fail, it will just return an empty object.

    See Also:
        `RFC 4466 2.1. <https://tools.ietf.org/html/rfc4466#section-2.1>`_

    Args:
        options: The mapping of options to argument.

    """

    _opt_pattern = re.compile(br'[a-zA-Z_.-][a-zA-Z0-9_.:-]*')
    _empty: Optional[ExtensionOptions] = None

    def __init__(self, options: Iterable[ExtensionOption]) -> None:
        super().__init__()
        self.options: Mapping[bytes, List] = \
            {opt.option: opt.arg for opt in options}
        self._raw: Optional[bytes] = None

    @classmethod
    def empty(cls) -> ExtensionOptions:
        """Return an empty set of command options."""
        if cls._empty is None:
            cls._empty = ExtensionOptions({})
        return cls._empty

    @property
    def value(self) -> Mapping[bytes, List]:
        return self.options

    def has(self, option: bytes) -> bool:
        return option in self.options

    def get(self, option: bytes) -> Optional[List]:
        return self.options.get(option, None)

    def __bool__(self) -> bool:
        return bool(self.options)

    def __len__(self) -> int:
        return len(self.options)

    def __bytes__(self) -> bytes:
        if self._raw is None:
            parts = [ExtensionOption(option, arg)
                     for option, arg in sorted(self.options.items())]
            self._raw = b'(' + BytesFormat(b' ').join(parts) + b')'
        return self._raw

    @classmethod
    def _parse_paren(cls, buf: memoryview, paren: bytes) -> memoryview:
        start = cls._whitespace_length(buf)
        if buf[start:start + 1] != paren:
            raise NotParseable(buf)
        return buf[start + 1:]

    @classmethod
    def _parse(cls, buf: memoryview, params: Params) \
            -> tuple[ExtensionOptions, memoryview]:
        buf = cls._parse_paren(buf, b'(')
        result: list[ExtensionOption] = []
        while True:
            try:
                option, buf = ExtensionOption.parse(buf, params)
            except NotParseable:
                break
            else:
                result.append(option)
        buf = cls._parse_paren(buf, b')')
        return cls(result), buf

    @classmethod
    def parse(cls, buf: memoryview, params: Params) \
            -> tuple[ExtensionOptions, memoryview]:
        try:
            return cls._parse(buf, params)
        except NotParseable:
            return cls.empty(), buf
