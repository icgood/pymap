
from abc import abstractmethod, ABCMeta
from typing import Type, Optional, Tuple, Iterable, Mapping, Sequence, List
from typing_extensions import Final

from .bytes import MaybeBytes, Writeable, BytesFormat
from .interfaces.message import MessageInterface, LoadedMessageInterface
from .parsing.primitives import Nil, Number, ListP, LiteralString
from .parsing.specials import DateTime, FetchAttribute, FetchValue
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

    __slots__ = ['_value']

    def __init__(self, attribute: FetchAttribute, msg: MessageInterface,
                 selected: SelectedMailbox) -> None:
        super().__init__(attribute)
        self._value = self._get_value(attribute, msg, selected)

    @classmethod
    @abstractmethod
    def _get_value(cls, attr: FetchAttribute, msg: MessageInterface,
                   selected: SelectedMailbox) -> MaybeBytes:
        ...

    def __bytes__(self) -> bytes:
        attr = self.attribute.for_response
        return BytesFormat(b'%b %b') % (attr, self._value)


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


class _LoadedFetchValue(FetchValue, metaclass=ABCMeta):

    __slots__ = ['_value']

    def __init__(self, attr: FetchAttribute, msg: MessageInterface,
                 loaded_msg: LoadedMessageInterface) -> None:
        if msg.expunged:
            raise NotFetchable(attr)
        super().__init__(attr)
        self._value = self._get_value(attr, loaded_msg)

    @abstractmethod
    def _get_value(self, attr: FetchAttribute,
                   loaded_msg: LoadedMessageInterface) -> Writeable:
        ...

    def __bytes__(self) -> bytes:
        attr = self.attribute.for_response
        return BytesFormat(b'%b %b') % (attr, self._value)

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

    __slots__ = ['message', 'loaded_msg', 'selected']

    def __init__(self, message: MessageInterface,
                 loaded_msg: LoadedMessageInterface,
                 selected: SelectedMailbox) -> None:
        super().__init__()
        self.message: Final = message
        self.loaded_msg: Final = loaded_msg
        self.selected: Final = selected

    def get_all(self, attributes: Iterable[FetchAttribute]) \
            -> Sequence[FetchValue]:
        """Return a list of all fetch values for the message.

        Args:
            attributes: The fetch attributes.

        """
        ret: List[FetchValue] = []
        for attr in attributes:
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
            return loaded(attr, self.message, self.loaded_msg)
        raise AttributeError(attr.value)
