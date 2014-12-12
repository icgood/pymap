
import re
import base64

from pymap.core import PymapError


class NotParseable(PymapError):
    """Indicates that the given buffer was not parseable by one or all of the
    data formats.

    """
    pass


class Data(object):
    """Represents a single data object from an IMAP stream. The sub-classes
    implement the different data formats.

    """

    @property
    def value(self):
        return self._val

    @classmethod
    def factory(cls, buf, start=0):
        pass


class Nil(Data):
    """Represents a NIL object from an IMAP stream.

    """

    _pattern = re.compile(r'[nN][iI][lL]')

    def __init__(self):
        super(Nil, self).__init__()
        self._val = None

    @classmethod
    def try_parse(cls, buf, start):
        match = cls._pattern.match(buf, start)
        if not match:
            raise NotParseable(buf)
        return cls(), match.end(1)

    def __bytes__(self):
        return b'NIL'


class Number(Data):
    """Represents a number object from an IMAP stream.

    :param int num: The number for the datum.

    """

    _pattern = re.compile(r'(\d+)')

    def __init__(self, num):
        super(Number, self).__init__()
        self._val = num

    @classmethod
    def try_parse(cls, buf, start):
        match = cls._pattern.match(buf, start)
        if not match:
            raise NotParseable(buf)
        return cls(int(match.group(1))), match.end(1)

    def __bytes__(self):
        return bytes(str(self._val).encode('ascii'))


class String(Data):
    """Represents a string object from an IMAP string.

    :param bytes string: The raw string for the datum.

    """

    _literal_pattern = re.compile(r'\{(\d+)\}\r?\n')

    def __init__(self, string):
        super(String, self).__init__()
        self._val = string

    @classmethod
    def try_parse(cls, buf, start):
        if buf[start:start+1] == b'"':
            return cls._try_quoted_parse(buf, start+1)
        match = cls._literal_pattern.match(buf, start)
        if match:
            literal_start = match.end(0)
            literal_end = literal_start + int(match.group(1))
            literal = buf[literal_start:literal_end]
            return cls(literal), literal_end
        raise NotParseable

    def __bytes__(self):
        return self._val


class List(Data):
    """Represents a list of :class:`Data` objects from an IMAP stream.

    :param items: Iterable of items, collected into a list, that make up the
                  datum.
    :type items: collections.abc.Iterable

    """

    _whitespace_pattern = re.compile(r'\w+')

    def __init__(self, items):
        super(List, self).__init__()
        self._val = list(items)

    @classmethod
    def try_parse(cls, buf, start):
        if buf[start:start+1] != b'(':
            raise NotParseable(buf)
        elif buf[start:start+2] == b'()':
            return cls([]), start+2
        items = []
        cur = start+1
        while True:
            item, cur = Data.factory(buf, cur)
            items.append(item)
            if buf[cur:cur+1] == b')':
                return cls(items), cur + 1
            match = cls._whitespace_pattern.match(buf, cur)
            if not match:
                raise NotParseable(buf)
            cur = match.end(0)

    def __bytes__(self):
        return b'(' + b' '.join([bytes(item) for item in self._val]) + b')'
