
from abc import abstractmethod, ABCMeta
from contextlib import contextmanager, asynccontextmanager
from typing import Type, Optional, Tuple, Iterator, Mapping, Sequence, List, \
    AsyncIterator
from typing_extensions import Final

from .bytes import BytesFormat, MaybeBytes, Writeable
from .interfaces.message import MessageInterface, LoadedMessageInterface
from .parsing.primitives import Nil, Number, ListP, LiteralString
from .parsing.specials import DateTime, FetchRequirement, FetchAttribute, \
    FetchValue
from .selected import SelectedMailbox

__all__ = ['NotFetchable', 'MessageAttributes']

_Partial = Optional[Tuple[int, Optional[int]]]


class NotFetchable(Exception):
    """Raised when a message cannot provide a
    :class:`~pymap.parsing.specials.fetchattr.FetchAttribute` for some reason,
    e.g. because it has been expunged.

    """

    def __init__(self, attr: FetchAttribute) -> None:
        attr_name = attr.value.decode('ascii')
        super().__init__(f'{attr_name} is not fetchable')
        self._attr = attr

    @property
    def attr(self) -> FetchAttribute:
        """The attribute that could not be fetched."""
        return self._attr


class _SimpleFetchValue(FetchValue, metaclass=ABCMeta):

    __slots__ = ['_msg', '_selected']

    def __init__(self, attribute: FetchAttribute, msg: MessageInterface,
                 selected: SelectedMailbox) -> None:
        super().__init__(attribute)
        self._msg = msg
        self._selected = selected

    @classmethod
    @abstractmethod
    def _get_value(cls, attr: FetchAttribute, msg: MessageInterface,
                   selected: SelectedMailbox) -> MaybeBytes:
        ...

    def __bytes__(self) -> bytes:
        return BytesFormat(b'%b %b') % (
            self.attribute.for_response,
            self._get_value(self.attribute, self._msg, self._selected))


class _UidFetchValue(_SimpleFetchValue):

    @classmethod
    def _get_value(cls, attr: FetchAttribute, msg: MessageInterface,
                   selected: SelectedMailbox) -> MaybeBytes:
        return Number(msg.uid)


class _FlagsFetchValue(_SimpleFetchValue):

    @classmethod
    def _get_value(cls, attr: FetchAttribute, msg: MessageInterface,
                   selected: SelectedMailbox) -> MaybeBytes:
        session_flags = selected.session_flags
        flag_set = msg.get_flags(session_flags)
        return ListP(flag_set, sort=True)


class _InternalDateFetchValue(_SimpleFetchValue):

    @classmethod
    def _get_value(cls, attr: FetchAttribute, msg: MessageInterface,
                   selected: SelectedMailbox) -> MaybeBytes:
        return DateTime(msg.internal_date)


class _EmailIdFetchValue(_SimpleFetchValue):

    @classmethod
    def _get_value(cls, attr: FetchAttribute, msg: MessageInterface,
                   selected: SelectedMailbox) -> MaybeBytes:
        if msg.expunged or msg.email_id is None:
            raise NotFetchable(attr)
        return msg.email_id.parens


class _ThreadIdFetchValue(_SimpleFetchValue):

    @classmethod
    def _get_value(cls, attr: FetchAttribute, msg: MessageInterface,
                   selected: SelectedMailbox) -> MaybeBytes:
        if msg.expunged:
            raise NotFetchable(attr)
        elif msg.thread_id is None:
            return Nil()
        else:
            return msg.thread_id.parens


class _LoadedMessageProvider:

    __slots__ = ['loaded_msg']

    def __init__(self) -> None:
        super().__init__()
        self.loaded_msg: Optional[LoadedMessageInterface] = None

    @contextmanager
    def apply(self, loaded_msg: LoadedMessageInterface) -> Iterator[None]:
        self.loaded_msg = loaded_msg
        try:
            yield
        finally:
            self.loaded_msg = None


class _LoadedFetchValue(FetchValue, metaclass=ABCMeta):

    _ellipsis = '\u2026'.encode('utf-8')

    __slots__ = ['_msg', '_get_loaded']

    def __init__(self, attr: FetchAttribute, msg: MessageInterface,
                 get_loaded: _LoadedMessageProvider) -> None:
        if msg.expunged:
            raise NotFetchable(attr)
        super().__init__(attr)
        self._msg = msg
        self._get_loaded = get_loaded

    @abstractmethod
    def _get_value(self, attr: FetchAttribute,
                   loaded_msg: LoadedMessageInterface) -> Writeable:
        ...

    def __bytes__(self) -> bytes:
        loaded_msg = self._get_loaded.loaded_msg
        if loaded_msg is None:
            value: MaybeBytes = self._ellipsis
        else:
            value = self._get_value(self.attribute, loaded_msg)
        return BytesFormat(b'%b %b') % (self.attribute.for_response, value)

    @classmethod
    def _get_data(cls, section: FetchAttribute.Section, partial: _Partial,
                  loaded_msg: LoadedMessageInterface, *,
                  binary: bool = False) -> Writeable:
        specifier = section.specifier
        parts = section.parts
        headers = section.headers
        if specifier is None:
            data = loaded_msg.get_body(parts, binary)
        elif specifier == b'MIME' and parts is not None:
            data = loaded_msg.get_headers(parts)
        elif specifier == b'TEXT':
            data = loaded_msg.get_message_text(parts)
        elif specifier == b'HEADER':
            data = loaded_msg.get_message_headers(parts)
        elif specifier == b'HEADER.FIELDS':
            data = loaded_msg.get_message_headers(parts, headers)
        elif specifier == b'HEADER.FIELDS.NOT':
            data = loaded_msg.get_message_headers(parts, headers, True)
        else:
            raise RuntimeError()  # Should not happen.
        return cls._get_partial(data, partial)

    @classmethod
    def _get_partial(cls, data: Writeable, partial: _Partial) -> Writeable:
        if partial is None:
            return data
        full = bytes(data)
        start, end = partial
        if end is None:
            end = len(full)
        return Writeable.wrap(full[start:end])


class _EnvelopeFetchValue(_LoadedFetchValue):

    def _get_value(self, attr: FetchAttribute,
                   loaded_msg: LoadedMessageInterface) -> Writeable:
        return loaded_msg.get_envelope_structure()


class _BodyStructureFetchValue(_LoadedFetchValue):

    def _get_value(self, attr: FetchAttribute,
                   loaded_msg: LoadedMessageInterface) -> Writeable:
        return loaded_msg.get_body_structure().extended


class _BodyFetchValue(_LoadedFetchValue):

    def _get_value(self, attr: FetchAttribute,
                   loaded_msg: LoadedMessageInterface) -> Writeable:
        attr = self.attribute
        if attr.section is None:
            return loaded_msg.get_body_structure()
        else:
            data = self._get_data(attr.section, attr.partial, loaded_msg)
            return LiteralString(data)


class _BodyPeekFetchValue(_BodyFetchValue):
    pass


class _RFC822FetchValue(_BodyFetchValue):
    pass


class _RFC822HeaderFetchValue(_BodyFetchValue):
    pass


class _RFC822TextFetchValue(_BodyFetchValue):
    pass


class _RFC822SizeFetchValue(_LoadedFetchValue):

    def _get_value(self, attr: FetchAttribute,
                   loaded_msg: LoadedMessageInterface) -> Writeable:
        return Number(loaded_msg.get_size())


class _BinaryFetchValue(_LoadedFetchValue):

    def _get_value(self, attr: FetchAttribute,
                   loaded_msg: LoadedMessageInterface) -> Writeable:
        attr = self.attribute
        if attr.section is None:
            raise RuntimeError()  # should not happen.
        data = self._get_data(attr.section, attr.partial, loaded_msg,
                              binary=True)
        return LiteralString(data, True)


class _BinaryPeekFetchValue(_BinaryFetchValue):
    pass


class _BinarySizeFetchValue(_LoadedFetchValue):

    def _get_value(self, attr: FetchAttribute,
                   loaded_msg: LoadedMessageInterface) -> Writeable:
        attr = self.attribute
        if attr.section is None:
            raise RuntimeError()  # should not happen.
        data = self._get_data(attr.section, attr.partial, loaded_msg,
                              binary=True)
        return Number(len(data))


class MessageAttributes:
    """Defines a re-usable object to query a
    :class:`~pymap.parsing.specials.fetchattr.FetchAttribute` from a message.

    Args:
        message: The message object.
        selected: The selected mailbox.

    """

    _simple_attrs: Mapping[bytes, Type[_SimpleFetchValue]] = {
        b'UID': _UidFetchValue,
        b'FLAGS': _FlagsFetchValue,
        b'INTERNALDATE': _InternalDateFetchValue,
        b'EMAILID': _EmailIdFetchValue,
        b'THREADID': _ThreadIdFetchValue}

    _loaded_attrs: Mapping[bytes, Type[_LoadedFetchValue]] = {
        b'ENVELOPE': _EnvelopeFetchValue,
        b'BODYSTRUCTURE': _BodyStructureFetchValue,
        b'BODY': _BodyFetchValue,
        b'BODY.PEEK': _BodyPeekFetchValue,
        b'RFC822': _RFC822FetchValue,
        b'RFC822.HEADER': _RFC822HeaderFetchValue,
        b'RFC822.TEXT': _RFC822TextFetchValue,
        b'RFC822.SIZE': _RFC822SizeFetchValue,
        b'BINARY': _BinaryFetchValue,
        b'BINARY.PEEK': _BinaryPeekFetchValue,
        b'BINARY.SIZE': _BinarySizeFetchValue}

    __slots__ = ['message', 'selected', 'attributes', 'requirement',
                 '_get_loader']

    def __init__(self, message: MessageInterface,
                 selected: SelectedMailbox,
                 attributes: Sequence[FetchAttribute]) -> None:
        super().__init__()
        self.message: Final = message
        self.selected: Final = selected
        self.attributes: Final = attributes
        self.requirement: Final = FetchRequirement.reduce(
            attr.requirement for attr in attributes)
        self._get_loader = _LoadedMessageProvider()

    @asynccontextmanager
    async def while_writing(self) -> AsyncIterator[None]:
        """While a fetch response is being written, it is wrapped in this
        context manager.

        """
        loaded_msg = await self.message.load_content(self.requirement)
        with self._get_loader.apply(loaded_msg):
            yield

    def get_all(self) -> Sequence[FetchValue]:
        """Return a list of all fetch values for the message."""
        ret: List[FetchValue] = []
        for attr in self.attributes:
            try:
                ret.append(self._get(attr))
            except NotFetchable:
                pass
        return ret

    def _get(self, attr: FetchAttribute) -> FetchValue:
        simple = self._simple_attrs.get(attr.value)
        if simple is not None:
            return simple(attr, self.message, self.selected)
        loaded = self._loaded_attrs.get(attr.value)
        if loaded is not None:
            return loaded(attr, self.message, self._get_loader)
        raise AttributeError(attr.value)
