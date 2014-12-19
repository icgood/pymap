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

from .. import NotParseable, Space, EndLine
from ..primitives import Atom, List
from ..specials import (AString, Mailbox, SequenceSet, Flag, FetchAttribute,
    SearchKey)
from . import CommandSelect, CommandNoArgs

__all__ = ['CheckCommand', 'CloseCommand', 'ExpungeCommand', 'CopyCommand',
           'FetchCommand', 'StoreCommand', 'UidCommand', 'SearchCommand']


class CheckCommand(CommandSelect, CommandNoArgs):
    command = b'CHECK'

CommandSelect.register_command(CheckCommand)


class CloseCommand(CommandSelect, CommandNoArgs):
    command = b'CLOSE'

CommandSelect.register_command(CloseCommand)


class ExpungeCommand(CommandSelect, CommandNoArgs):
    command = b'EXPUNGE'

CommandSelect.register_command(ExpungeCommand)


class CopyCommand(CommandSelect):
    command = b'COPY'

    def __init__(self, tag, seq_set, mailbox, uid=False):
        super(CopyCommand, self).__init__(tag)
        self.sequence_set = seq_set
        self.mailbox = mailbox
        self.uid = uid

    @classmethod
    def _parse(cls, tag, buf, uid=False, **kwargs):
        _, buf = Space.parse(buf)
        seq_set, buf = SequenceSet.parse(buf)
        _, buf = Space.parse(buf)
        mailbox, buf = Mailbox.parse(buf)
        _, buf = EndLine.parse(buf)
        return cls(tag, seq_set.sequences, mailbox.value, uid=uid), buf

CommandSelect.register_command(CopyCommand)


class FetchCommand(CommandSelect):
    command = b'FETCH'

    def __init__(self, tag, seq_set, attr_list):
        super(FetchCommand, self).__init__(tag)
        self.sequence_set = seq_set
        self.attributes = attr_list

    @classmethod
    def _check_macros(cls, buf):
        atom, after = Atom.parse(buf)
        macro = atom.value.upper()
        if macro == b'ALL':
            attrs = [FetchAttribute(b'FLAGS'),
                     FetchAttribute(b'INTERNALDATE'),
                     FetchAttribute(b'RFC822.SIZE'),
                     FetchAttribute(b'Envelope')]
            return attrs, after
        elif macro == b'FULL':
            attrs = [FetchAttribute(b'FLAGS'),
                     FetchAttribute(b'INTERNALDATE'),
                     FetchAttribute(b'RFC822.SIZE')]
            return attrs, after
        elif macro == b'FAST':
            attrs = [FetchAttribute(b'FLAGS'),
                     FetchAttribute(b'INTERNALDATE'),
                     FetchAttribute(b'RFC822.SIZE'),
                     FetchAttribute(b'Envelope'),
                     FetchAttribute(b'BODY')]
            return attrs, after
        raise NotParseable(buf)

    @classmethod
    def _parse(cls, tag, buf, uid=False, **kwargs):
        _, buf = Space.parse(buf)
        seq_set, buf = SequenceSet.parse(buf)
        _, buf = Space.parse(buf)
        try:
            attrs, buf = cls._check_macros(buf)
        except NotParseable:
            pass
        else:
            return cls(tag, seq_set.sequences, attrs), buf
        try:
            attr, buf = FetchAttribute.parse(buf)
        except NotParseable:
            pass
        else:
            return cls(tag, seq_set.sequences, [attr]), buf
        attr_list, buf = List.parse(buf, list_expected=[FetchAttribute])
        return cls(tag, seq_set.sequences, attr_list.value, uid=uid), buf

CommandSelect.register_command(FetchCommand)


class StoreCommand(CommandSelect):
    command = b'STORE'

    _info_pattern = re.compile(br'^([+-]?)FLAGS(\.SILENT)?$', re.I)
    _modes = {b'': 'replace', b'+': 'add', b'-': 'subtract'}

    def __init__(self, tag, seq_set, flag_list,
                 uid=False, mode='replace', silent=False):
        super(StoreCommand, self).__init__(tag)
        self.sequence_set = seq_set
        self.flag_list = flag_list
        self.uid = uid
        self.mode = mode
        self.silent = silent

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
    def _parse(cls, tag, buf, uid=False, **kwargs):
        _, buf = Space.parse(buf)
        seq_set, buf = SequenceSet.parse(buf)
        _, buf = Space.parse(buf)
        info, buf = cls._parse_store_info(buf)
        _, buf = Space.parse(buf)
        flag_list, buf = cls._parse_flag_list(buf)
        _, buf = EndLine.parse(buf)
        return cls(tag, seq_set.sequences, flag_list, uid=uid, **info), buf

CommandSelect.register_command(StoreCommand)


class UidCommand(CommandSelect):
    command = b'UID'

    @classmethod
    def _parse(cls, tag, buf, **kwargs):
        for cmd in [CopyCommand, FetchCommand, SearchCommand, StoreCommand]:
            try:
                return cmd._parse(tag, buf, uid=True, **kwargs)
            except NotParseable:
                pass
        raise NotParseable(buf)

CommandSelect.register_command(UidCommand)


class SearchCommand(CommandSelect):
    command = b'SEARCH'

    def __init__(self, tag, keys, charset=None, uid=None):
        super(SearchCommand, self).__init__(tag)
        self.keys = keys
        self.charset = charset
        self.uid = uid

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
                    raise BadCharset(buf)
                return charset, after
        return 'US-ASCII', buf

    @classmethod
    def _parse(cls, tag, buf, uid=False, **kwargs):
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
            else:
                continue
        return cls(tag, search_keys, charset=charset, uid=uid), buf

CommandSelect.register_command(SearchCommand)
