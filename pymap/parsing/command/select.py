# Copyright (c) 2014 Ian C. Good
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#

import re
from typing import Tuple, FrozenSet

from pymap.flag import FlagOp
from . import CommandSelect, CommandNoArgs
from .. import NotParseable, Space, EndLine, Buffer
from ..primitives import Atom, List
from ..specials import (AString, Mailbox, SequenceSet, Flag, FetchAttribute,
                        SearchKey)

__all__ = ['CheckCommand', 'CloseCommand', 'ExpungeCommand', 'CopyCommand',
           'FetchCommand', 'StoreCommand', 'SearchCommand', 'UidCommand']


class CheckCommand(CommandSelect, CommandNoArgs):
    command = b'CHECK'


class CloseCommand(CommandSelect, CommandNoArgs):
    command = b'CLOSE'


class ExpungeCommand(CommandSelect, CommandNoArgs):
    command = b'EXPUNGE'


class CopyCommand(CommandSelect):
    command = b'COPY'

    def __init__(self, tag, seq_set, mailbox):
        super().__init__(tag)
        self.sequence_set = seq_set  # type: SequenceSet
        self.mailbox_obj = mailbox  # type: Mailbox

    @property
    def with_uid(self) -> bool:
        return self.sequence_set.uid

    @property
    def mailbox(self) -> str:
        return str(self.mailbox_obj)

    @classmethod
    def parse(cls, buf: Buffer, tag: bytes = None, uid: bool = False, **_) \
            -> Tuple['CopyCommand', bytes]:
        _, buf = Space.parse(buf)
        seq_set, buf = SequenceSet.parse(buf, uid=uid)
        _, buf = Space.parse(buf)
        mailbox, buf = Mailbox.parse(buf)
        _, buf = EndLine.parse(buf)
        return cls(tag, seq_set, mailbox), buf


class FetchCommand(CommandSelect):
    command = b'FETCH'

    def __init__(self, tag, seq_set, attr_set):
        super().__init__(tag)
        self.sequence_set = seq_set  # type: SequenceSet
        self.no_expunge_response = not seq_set.uid  # type: bool
        self.attributes = (
                frozenset(attr_set)
        ) # type: FrozenSet[FetchAttribute]

    @property
    def with_uid(self) -> bool:
        return self.sequence_set.uid

    @classmethod
    def _check_macros(cls, buf):
        atom, after = Atom.parse(buf)
        macro = atom.value.upper()
        if macro == b'ALL':
            attrs = {FetchAttribute(b'FLAGS'), FetchAttribute(b'INTERNALDATE'),
                     FetchAttribute(b'RFC822.SIZE'),
                     FetchAttribute(b'ENVELOPE')}
            return attrs, after
        elif macro == b'FULL':
            attrs = {FetchAttribute(b'FLAGS'), FetchAttribute(b'INTERNALDATE'),
                     FetchAttribute(b'RFC822.SIZE'),
                     FetchAttribute(b'ENVELOPE'), FetchAttribute(b'BODY')}
            return attrs, after
        elif macro == b'FAST':
            attrs = {FetchAttribute(b'FLAGS'), FetchAttribute(b'INTERNALDATE'),
                     FetchAttribute(b'RFC822.SIZE')}
            return attrs, after
        raise NotParseable(buf)

    @classmethod
    def parse(cls, buf: Buffer, tag: bytes = None, uid: bool = False, **_) \
            -> Tuple['FetchCommand', bytes]:
        _, buf = Space.parse(buf)
        seq_set, buf = SequenceSet.parse(buf, uid=uid)
        _, buf = Space.parse(buf)
        attr_set = set()
        try:
            attr_set, buf = cls._check_macros(buf)
        except NotParseable:
            pass
        try:
            attr, buf = FetchAttribute.parse(buf)
            attr_set = {attr}
        except NotParseable:
            pass
        if not attr_set:
            attr_list, buf = List.parse(buf, list_expected=[FetchAttribute])
            attr_set = set(attr_list.value)
        if uid:
            attr_set.add(FetchAttribute(b'UID'))
        _, buf = EndLine.parse(buf)
        return cls(tag, seq_set, attr_set), buf


class StoreCommand(CommandSelect):
    command = b'STORE'

    _info_pattern = re.compile(br'^([+-]?)FLAGS(\.SILENT)?$', re.I)
    _modes = {b'': 'replace', b'+': 'add', b'-': 'subtract'}

    def __init__(self, tag, seq_set, flags, mode=FlagOp.REPLACE, silent=False):
        super().__init__(tag)
        self.sequence_set = seq_set  # type: SequenceSet
        self.flag_set = frozenset(flags)  # type: FrozenSet[Flag]
        self.mode = mode  # type: FlagOp
        self.silent = silent  # type: bool
        self.no_expunge_response = not seq_set.uid  # type: bool

    @property
    def with_uid(self) -> bool:
        return self.sequence_set.uid

    @classmethod
    def _parse_store_info(cls, buf):
        info, after = Atom.parse(buf)
        match = cls._info_pattern.match(info.value)
        if not match:
            raise NotParseable(buf)
        mode = cls._modes[match.group(1)]
        silent = bool(match.group(2))
        return {'mode': mode, 'silent': silent}, after

    @classmethod
    def _parse_flag_list(cls, buf):
        try:
            flag_list, buf = List.parse(buf, list_expected=[Flag])
        except NotParseable:
            pass
        else:
            return flag_list.value, buf
        flag_list = []
        while True:
            try:
                flag, buf = Flag.parse(buf)
                flag_list.append(flag)
                _, buf = Space.parse(buf)
            except NotParseable:
                return flag_list, buf

    @classmethod
    def parse(cls, buf: Buffer, tag: bytes = None, uid: bool = False, **_) \
            -> Tuple['StoreCommand', bytes]:
        _, buf = Space.parse(buf)
        seq_set, buf = SequenceSet.parse(buf, uid=uid)
        _, buf = Space.parse(buf)
        info, buf = cls._parse_store_info(buf)
        _, buf = Space.parse(buf)
        flag_list, buf = cls._parse_flag_list(buf)
        _, buf = EndLine.parse(buf)
        return cls(tag, seq_set, flag_list, **info), buf


class SearchCommand(CommandSelect):
    command = b'SEARCH'

    def __init__(self, tag, keys, charset=None, uid=False):
        super().__init__(tag)
        self.keys = frozenset(keys)  # type: FrozenSet[SearchKey]
        self.charset = charset  # type: str
        self._with_uid = uid  # type: bool
        self.no_expunge_response = not uid  # type: bool

    @property
    def with_uid(self) -> bool:
        return self._with_uid

    @classmethod
    def _parse_charset(cls, buf, **kwargs):
        try:
            _, after = Space.parse(buf)
            atom, after = Atom.parse(after)
        except NotParseable:
            pass
        else:
            if atom.value.upper() == b'CHARSET':
                _, after = Space.parse(after)
                string, after = AString.parse(after, **kwargs)
                charset = str(string.value, 'ascii')
                try:
                    b' '.decode(charset)
                except LookupError:
                    raise NotParseable(buf)
                return charset, after
        return 'US-ASCII', buf

    @classmethod
    def parse(cls, buf: Buffer, tag: bytes = None, uid: bool = False,
              **kwargs) -> Tuple['SearchCommand', bytes]:
        charset, buf = cls._parse_charset(buf, **kwargs)
        search_keys = []
        while True:
            try:
                _, buf = Space.parse(buf)
                key, buf = SearchKey.parse(buf, charset=charset, **kwargs)
                search_keys.append(key)
            except NotParseable:
                if not search_keys:
                    raise
                break
        _, buf = EndLine.parse(buf)
        return cls(tag, search_keys, charset=charset, uid=uid), buf


class UidCommand(CommandSelect):
    command = b'UID'

    _allowed_subcommands = {b'COPY': CopyCommand,
                            b'FETCH': FetchCommand,
                            b'SEARCH': SearchCommand,
                            b'STORE': StoreCommand}

    @classmethod
    def parse(cls, buf: Buffer, tag: bytes = None, **kwargs) \
            -> Tuple[CommandSelect, bytes]:
        _, buf = Space.parse(buf)
        atom, after = Atom.parse(buf)
        cmd = cls._allowed_subcommands.get(atom.value.upper())
        if not cmd:
            raise NotParseable(buf)
        return cmd.parse(after, tag=tag, uid=True, **kwargs)
