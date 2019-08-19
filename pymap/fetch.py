
from typing import Optional, Tuple, Iterable, Sequence, List
from typing_extensions import Final

from .bytes import MaybeBytes, Writeable
from .exceptions import NotSupportedError
from .interfaces.message import MessageInterface
from .parsing.primitives import Nil, Number, ListP, LiteralString
from .parsing.specials import DateTime, FetchAttribute
from .selected import SelectedMailbox

__all__ = ['NotFetchable', 'MessageAttributes']

_Partial = Optional[Tuple[int, Optional[int]]]


def _not_expunged(orig):
    def deco(self: 'MessageAttributes', attr: FetchAttribute,
             *args, **kwargs) -> MaybeBytes:
        if self.message.expunged:
            raise NotFetchable(attr)
        else:
            return orig(self, attr, *args, **kwargs)
    return deco


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


class MessageAttributes:
    """Defines a re-usable object to query a
    :class:`~pymap.parsing.specials.fetchattr.FetchAttribute` from a message.

    Args:
        message: The message object.
        selected: The selected mailbox.

    """

    def __init__(self, message: MessageInterface,
                 selected: SelectedMailbox) -> None:
        super().__init__()
        self.message: Final = message
        self.selected: Final = selected

    def get_all(self, attrs: Iterable[FetchAttribute]) \
            -> Sequence[Tuple[FetchAttribute, MaybeBytes]]:
        """Return a list of tuples containing the attribute iself and the bytes
        representation of that attribute from the message.

        Args:
            attrs: The fetch attributes.

        """
        ret: List[Tuple[FetchAttribute, MaybeBytes]] = []
        for attr in attrs:
            try:
                ret.append((attr.for_response, self.get(attr)))
            except NotFetchable:
                pass
        return ret

    def get(self, attr: FetchAttribute) -> MaybeBytes:
        """Return the bytes representation of the given message attribue.

        Args:
            attr: The fetch attribute.

        Raises:
            :class:`NotFetchable`

        """
        attr_name = attr.value.decode('ascii')
        method = getattr(self, '_get_' + attr_name.replace('.', '_'))
        return method(attr)

    def _get_data(self, section: FetchAttribute.Section, partial: _Partial, *,
                  binary: bool = False) -> Writeable:
        msg = self.message
        specifier = section.specifier
        parts = section.parts
        headers = section.headers
        if specifier is None:
            data = msg.get_body(parts, binary)
        elif specifier == b'MIME' and parts is not None:
            data = msg.get_headers(parts)
        elif specifier == b'TEXT':
            data = msg.get_message_text(parts)
        elif specifier == b'HEADER':
            data = msg.get_message_headers(parts)
        elif specifier == b'HEADER.FIELDS':
            data = msg.get_message_headers(parts, headers)
        elif specifier == b'HEADER.FIELDS.NOT':
            data = msg.get_message_headers(parts, headers, True)
        else:
            raise RuntimeError()  # Should not happen.
        return self._get_partial(data, partial)

    def _get_partial(self, data: Writeable, partial: _Partial) -> Writeable:
        if partial is None:
            return data
        full = bytes(data)
        start, end = partial
        if end is None:
            end = len(full)
        return Writeable.wrap(full[start:end])

    def _get_UID(self, attr: FetchAttribute) -> MaybeBytes:
        return Number(self.message.uid)

    def _get_FLAGS(self, attr: FetchAttribute) -> MaybeBytes:
        session_flags = self.selected.session_flags
        flag_set = self.message.get_flags(session_flags)
        return ListP(flag_set, sort=True)

    def _get_INTERNALDATE(self, attr: FetchAttribute) -> MaybeBytes:
        return DateTime(self.message.internal_date)

    @_not_expunged
    def _get_EMAILID(self, attr: FetchAttribute) -> MaybeBytes:
        if self.message.email_id is None:
            raise NotSupportedError('EMAILID not supported.')
        return self.message.email_id.parens

    @_not_expunged
    def _get_THREADID(self, attr: FetchAttribute) -> MaybeBytes:
        if self.message.thread_id is None:
            return Nil()
        else:
            return self.message.thread_id.parens

    @_not_expunged
    def _get_ENVELOPE(self, attr: FetchAttribute) -> MaybeBytes:
        return self.message.get_envelope_structure()

    @_not_expunged
    def _get_BODYSTRUCTURE(self, attr: FetchAttribute) -> MaybeBytes:
        return self.message.get_body_structure().extended

    @_not_expunged
    def _get_BODY(self, attr: FetchAttribute) -> MaybeBytes:
        if attr.section is None:
            return self.message.get_body_structure()
        return LiteralString(self._get_data(attr.section, attr.partial))

    @_not_expunged
    def _get_BODY_PEEK(self, attr: FetchAttribute) -> MaybeBytes:
        return self._get_BODY(attr)

    @_not_expunged
    def _get_RFC822(self, attr: FetchAttribute) -> MaybeBytes:
        return self._get_BODY(attr)

    @_not_expunged
    def _get_RFC822_HEADER(self, attr: FetchAttribute) -> MaybeBytes:
        return self._get_BODY(attr)

    @_not_expunged
    def _get_RFC822_TEXT(self, attr: FetchAttribute) -> MaybeBytes:
        return self._get_BODY(attr)

    @_not_expunged
    def _get_RFC822_SIZE(self, attr: FetchAttribute) -> MaybeBytes:
        return Number(self.message.get_size())

    @_not_expunged
    def _get_BINARY(self, attr: FetchAttribute) -> MaybeBytes:
        if attr.section is None:
            raise RuntimeError()  # should not happen.
        data = self._get_data(attr.section, attr.partial, binary=True)
        return LiteralString(data, True)

    @_not_expunged
    def _get_BINARY_PEEK(self, attr: FetchAttribute) -> MaybeBytes:
        return self._get_BINARY(attr)

    @_not_expunged
    def _get_BINARY_SIZE(self, attr: FetchAttribute) -> MaybeBytes:
        if attr.section is None:
            raise RuntimeError()  # should not happen.
        data = self._get_data(attr.section, attr.partial, binary=True)
        return Number(len(data))
