
from __future__ import annotations

from abc import abstractmethod, ABCMeta
from collections.abc import Iterator, Mapping, Sequence, AsyncIterator
from contextlib import contextmanager, asynccontextmanager
from typing import ClassVar, Optional, Final, Protocol

from .bytes import BytesFormat, MaybeBytes, Writeable
from .interfaces.message import MessageInterface, LoadedMessageInterface
from .parsing.primitives import Nil, Number, List, LiteralString
from .parsing.specials import DateTime, FetchRequirement, FetchAttribute, \
    FetchValue
from .selected import SelectedMailbox

__all__ = ['LoadedMessageProvider', 'DynamicFetchValue',
           'DynamicLoadedFetchValue', 'MessageAttributes']

_Partial = Optional[tuple[int, Optional[int]]]


class LoadedMessageProvider(Protocol):
    """Generic protocol that provides access to a message's loaded contents
    when they are available.

    """

    @property
    @abstractmethod
    def loaded_msg(self) -> Optional[LoadedMessageInterface]:
        """The loaded message, if available."""


class DynamicFetchValue(FetchValue, metaclass=ABCMeta):
    """Base class for fetch values that are dynamically read from a message.

    Args:
        attribute: The fetch attribute.
        message: The message object.
        selected: The selected mailbox.

    """

    __slots__ = ['message', 'selected']

    def __init__(self, attribute: FetchAttribute, *,
                 message: MessageInterface, selected: SelectedMailbox) -> None:
        super().__init__(attribute)
        self.message: Final = message
        self.selected: Final = selected

    @abstractmethod
    def get_value(self) -> MaybeBytes:
        """Computes the value of the fetch attribute for the message."""
        ...

    def __bytes__(self) -> bytes:
        return BytesFormat(b'%b %b') % (
            self.attribute.for_response, self.get_value())


class DynamicLoadedFetchValue(FetchValue, metaclass=ABCMeta):
    """Base class for fetch values that are dynamically read from a message and
    require loading its contents.

    Args:
        attribute: The fetch attribute.
        message: The message object.
        selected: The selected mailbox.
        get_loaded: The provider of the loaded message contents, if available.

    """

    __slots__ = ['message', '_get_loaded']

    def __init__(self, attribute: FetchAttribute, *,
                 message: MessageInterface,
                 get_loaded: LoadedMessageProvider) -> None:
        super().__init__(attribute)
        self.message: Final = message
        self._get_loaded = get_loaded

    @abstractmethod
    def get_value(self, loaded_msg: LoadedMessageInterface) -> MaybeBytes:
        """Computes the value of the fetch attribute for the message.

        Args:
            loaded_msg: The loaded message object.

        """
        ...

    def __bytes__(self) -> bytes:
        loaded_msg = self._get_loaded.loaded_msg
        if loaded_msg is None:
            value: MaybeBytes = MessageAttributes.placeholder
        else:
            value = self.get_value(loaded_msg)
        return BytesFormat(b'%b %b') % (
            self.attribute.for_response, value)

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


class _UidFetchValue(DynamicFetchValue):

    def get_value(self) -> MaybeBytes:
        return Number(self.message.uid)


class _FlagsFetchValue(DynamicFetchValue):

    def get_value(self) -> MaybeBytes:
        session_flags = self.selected.session_flags
        flag_set = self.message.get_flags(session_flags)
        return List(flag_set, sort=True)


class _InternalDateFetchValue(DynamicFetchValue):

    def get_value(self) -> MaybeBytes:
        return DateTime(self.message.internal_date)


class _EmailIdFetchValue(DynamicFetchValue):

    def get_value(self) -> MaybeBytes:
        return self.message.email_id.parens


class _ThreadIdFetchValue(DynamicFetchValue):

    def get_value(self) -> MaybeBytes:
        try:
            return self.message.thread_id.parens
        except ValueError:
            return Nil()


class _LoadedMessageProvider(LoadedMessageProvider):

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


class _EnvelopeFetchValue(DynamicLoadedFetchValue):

    def get_value(self, loaded_msg: LoadedMessageInterface) -> MaybeBytes:
        return loaded_msg.get_envelope_structure()


class _BodyStructureFetchValue(DynamicLoadedFetchValue):

    def get_value(self, loaded_msg: LoadedMessageInterface) -> MaybeBytes:
        return loaded_msg.get_body_structure().extended


class _BodyFetchValue(DynamicLoadedFetchValue):

    def get_value(self, loaded_msg: LoadedMessageInterface) -> MaybeBytes:
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


class _RFC822SizeFetchValue(DynamicLoadedFetchValue):

    def get_value(self, loaded_msg: LoadedMessageInterface) -> MaybeBytes:
        return Number(loaded_msg.get_size())


class _BinaryFetchValue(DynamicLoadedFetchValue):

    def get_value(self, loaded_msg: LoadedMessageInterface) -> MaybeBytes:
        attr = self.attribute
        if attr.section is None:
            raise RuntimeError()  # should not happen.
        data = self._get_data(attr.section, attr.partial, loaded_msg,
                              binary=True)
        return LiteralString(data, True)


class _BinaryPeekFetchValue(_BinaryFetchValue):
    pass


class _BinarySizeFetchValue(DynamicLoadedFetchValue):

    def get_value(self, loaded_msg: LoadedMessageInterface) -> MaybeBytes:
        attr = self.attribute
        if attr.section is None:
            raise RuntimeError()  # should not happen.
        data = self._get_data(attr.section, attr.partial, loaded_msg,
                              binary=True)
        return Number(len(data))


class MessageAttributes(Sequence[FetchValue]):
    """Defines the logic for how fetch attributes are resolved on a message to
    produce a fetch value.

    Args:
        message: The message object.
        selected: The selected mailbox.

    """

    #: Placeholder value for fetch values requiring loaded message contents.
    placeholder: ClassVar[bytes] = b'...'

    _simple_attrs: Mapping[bytes, type[DynamicFetchValue]] = {
        b'UID': _UidFetchValue,
        b'FLAGS': _FlagsFetchValue,
        b'INTERNALDATE': _InternalDateFetchValue,
        b'EMAILID': _EmailIdFetchValue,
        b'THREADID': _ThreadIdFetchValue}

    _loaded_attrs: Mapping[bytes, type[DynamicLoadedFetchValue]] = {
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
                 '_get_loaded', '_values']

    def __init__(self, message: MessageInterface,
                 selected: SelectedMailbox,
                 attributes: Sequence[FetchAttribute]) -> None:
        super().__init__()
        self.message: Final = message
        self.selected: Final = selected
        self.attributes: Final = attributes
        self.requirement: Final = FetchRequirement.reduce(
            attr.requirement for attr in attributes)
        self._get_loaded = _LoadedMessageProvider()
        self._values: Optional[Sequence[FetchValue]] = None

    @asynccontextmanager
    async def load_hook(self) -> AsyncIterator[None]:
        """An async context manager that loads the message content on entry,
        and releases it on exit. Fetch values that require loaded message
        content will write :attr:`.placeholder` if written outside of this
        context manager, for console or log output.

        """
        loaded_msg = await self.message.load_content(self.requirement)
        with self._get_loaded.apply(loaded_msg):
            yield

    def __iter__(self) -> Iterator[FetchValue]:
        return iter(self._get_values())

    def __getitem__(self, index):
        values = self._get_values()
        return values[index]

    def __len__(self) -> int:
        return len(self.attributes)

    def _get_values(self) -> Sequence[FetchValue]:
        if self._values is None:
            self._values = [self._get(attr) for attr in self.attributes]
        return self._values

    def _get(self, attr: FetchAttribute) -> FetchValue:
        attr_name = attr.value
        simple = self._simple_attrs.get(attr_name)
        if simple is not None:
            return simple(attr, message=self.message, selected=self.selected)
        loaded = self._loaded_attrs.get(attr_name)
        if loaded is not None:
            return loaded(attr, message=self.message,
                          get_loaded=self._get_loaded)
        raise KeyError(attr_name)
