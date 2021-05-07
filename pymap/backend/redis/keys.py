
from __future__ import annotations

from abc import abstractmethod, ABCMeta
from collections.abc import Sequence, Mapping
from typing import Union, Final

from pymap.bytes import MaybeBytes, BytesFormat

__all__ = ['RedisKey', 'KeysGroup', 'GlobalKeys', 'CleanupKeys',
           'NamespaceKeys', 'ContentKeys', 'FilterKeys', 'MailboxKeys']

#: The version number of this key layout, to track backwards incompatible
#: changes.
DATA_VERSION: Final = 4

_Value = Union[int, MaybeBytes]


class RedisKey:
    """Defines complex redis keys using composite segments.

    Args:
        joiner: The object used to join segments.
        segments: The current list of key segments.
        named: A mapping of named segments.

    """

    __slots__ = ['joiner', 'segments', 'named']

    def __init__(self, joiner: BytesFormat, segments: Sequence[_Value],
                 named: Mapping[str, bytes]) -> None:
        super().__init__()
        self.joiner: Final = joiner
        self.segments: Final = segments
        self.named: Final = named

    def fork(self, segment: _Value, *, name: str = None) -> RedisKey:
        """Fork a new redis key adding a new segment.

        Args:
            segment: The new key segment to append.
            name: An optional name to assign to the value.

        """
        new_segments = list(self.segments)
        new_segments.append(segment)
        if name is not None:
            new_named = dict(self.named)
            new_named[name] = bytes(segment)
            return RedisKey(self.joiner, new_segments, new_named)
        else:
            return RedisKey(self.joiner, new_segments, self.named)

    def end(self, *segments: _Value) -> bytes:
        """Terminate the redis key producing a bytestring.

        Args:
            segments: Optional segments to add to the result.

        """
        return self.joiner.join(self.segments, segments)


class KeysGroup(metaclass=ABCMeta):
    """A group of redis keys that are related and contained in the same root
    key.

    Args:
        root: The root redis key.

    """

    __slots__ = ['root']

    def __init__(self, root: RedisKey) -> None:
        super().__init__()
        self.root = root

    @property
    @abstractmethod
    def keys(self) -> Sequence[bytes]:
        """All the keys in the group, not including nested key groups."""
        ...


class GlobalKeys(KeysGroup):
    """The key group that is considered global. New :attr:`DATA_VERSION` values
    must be compatible with these keys.

    Args:
        root: The root redis key.

    """

    __slots__ = ['cleanup_root', 'namespace_root', 'namespaces']

    def __init__(self, root: RedisKey) -> None:
        super().__init__(root)
        self.cleanup_root: Final = root.fork(b'cleanup')
        self.namespace_root: Final = root.fork(b'ns')
        self.namespaces: Final = root.end(b'ns')

    @property
    def keys(self) -> Sequence[bytes]:
        return [self.namespaces]


class CleanupKeys(KeysGroup):
    """The key group for cleaning up keys that are no longer active.

    Args:
        root: The root redis key.

    """

    __slots__ = ['namespaces', 'mailboxes', 'contents']

    def __init__(self, parent: GlobalKeys) -> None:
        root = parent.cleanup_root.fork(DATA_VERSION, name='version')
        super().__init__(root)
        self.namespaces: Final = root.end(b'ns')
        self.mailboxes: Final = root.end(b'mbx')
        self.contents: Final = root.end(b'content')

    @property
    def keys(self) -> Sequence[bytes]:
        return [self.namespaces, self.mailboxes, self.contents]


class NamespaceKeys(KeysGroup):
    """The key group for managing mailbox namespaces, groups of mailboxes that
    typically correspond to a login user.

    Args:
        root: The root redis key.
        namespace: The namespace ID.

    """

    __slots__ = ['mailbox_root', 'content_root', 'mailboxes', 'max_order',
                 'order', 'uid_validity', 'subscribed', 'content_refs',
                 'thread_keys', 'max_modseq']

    def __init__(self, parent: GlobalKeys, namespace: _Value) -> None:
        root = parent.namespace_root.fork(namespace, name='namespace')
        super().__init__(root)
        self.mailbox_root: Final = root.fork(b'mbx')
        self.content_root: Final = root.fork(b'content')
        self.mailboxes: Final = root.end(b'mailboxes')
        self.max_order: Final = root.end(b'max-order')
        self.order: Final = root.end(b'order')
        self.uid_validity: Final = root.end(b'uidv')
        self.subscribed: Final = root.end(b'subscribed')
        self.content_refs: Final = root.end(b'contentrefs')
        self.thread_keys: Final = root.end(b'threadkeys')
        self.max_modseq: Final = root.end(b'maxmodseq')

    @property
    def keys(self) -> Sequence[bytes]:
        return [self.mailboxes, self.max_order, self.order, self.uid_validity,
                self.subscribed, self.content_refs, self.thread_keys,
                self.max_modseq]


class ContentKeys(KeysGroup):
    """The key group for managing the content of messages.

    Args:
        root: The root redis key.
        email_id: The email object ID.

    """

    __slots__ = ['data']

    def __init__(self, parent: NamespaceKeys, email_id: _Value) -> None:
        root = parent.content_root.fork(email_id, name='email_id')
        super().__init__(root)
        self.data: Final = root.end()

    @property
    def keys(self) -> Sequence[bytes]:
        return [self.data]


class FilterKeys(KeysGroup):
    """The key group for managing filters.

    Args:
        root: The root redis key.

    """

    __slots__ = ['data', 'names']

    def __init__(self, parent: NamespaceKeys) -> None:
        root = parent.root.fork(b'sieve')
        super().__init__(root)
        self.data: Final = root.end(b'data')
        self.names: Final = root.end(b'names')

    @property
    def keys(self) -> Sequence[bytes]:
        return [self.data, self.names]


class MailboxKeys(KeysGroup):
    """The key group for managing a single mailbox.

    Args:
        root: The root redis key.
        mailbox_id: The mailbox object ID.

    """

    __slots__ = ['max_uid', 'uids', 'seq', 'content', 'changes', 'recent',
                 'deleted', 'unseen']

    def __init__(self, parent: NamespaceKeys, mailbox_id: _Value) -> None:
        root = parent.mailbox_root.fork(mailbox_id, name='mailbox_id')
        super().__init__(root)
        self.max_uid: Final = root.end(b'max-uid')
        self.uids: Final = root.end(b'uids')
        self.seq: Final = root.end(b'seq')
        self.content: Final = root.end(b'content')
        self.changes: Final = root.end(b'changes')
        self.recent: Final = root.end(b'recent')
        self.deleted: Final = root.end(b'deleted')
        self.unseen: Final = root.end(b'unseen')

    @property
    def keys(self) -> Sequence[bytes]:
        return [self.max_uid, self.uids, self.seq, self.content, self.changes,
                self.recent, self.deleted, self.unseen]
