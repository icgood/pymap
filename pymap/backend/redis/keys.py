
from abc import abstractmethod, ABCMeta
from typing import Union, Optional, Mapping, Sequence
from typing_extensions import Final

from pymap.bytes import MaybeBytes

__all__ = ['RedisKey', 'KeysGroup', 'CleanupKeys', 'NamespaceKeys',
           'MailboxKeys', 'MessageKeys']

_Value = Union[int, MaybeBytes]


class RedisKey:
    """Defines key templates for composing complex redis keys.

    Args:
        template: The key template bytestring.
        args: The known remaining arguments for the template.

    """

    __slots__ = ['template', 'args']

    def __init__(self, template: bytes, args: Mapping[bytes, bytes]) -> None:
        super().__init__()
        self.template: Final = template
        self.args: Final = args

    def _add_suffix(self, suffix: Optional[bytes]) -> bytes:
        if suffix is None:
            return self.template
        else:
            return self.template + suffix

    def _add_kw(self, args: Mapping[str, _Value]) -> Mapping[bytes, bytes]:
        if not args:
            return self.args
        new_args = dict(self.args)
        for name, val in args.items():
            if isinstance(val, int):
                val_bytes = b'%d' % val
            elif isinstance(val, bytes):
                val_bytes = val
            else:
                val_bytes = bytes(val)
            new_args[name.encode('ascii')] = val_bytes
        return new_args

    def end(self, suffix: bytes = None, **args: _Value) -> bytes:
        """Complete the template, returning the resulting bytestring.

        Args:
            suffix: The bytestring appended to the current template, which may
                contain new template arguments.
            args: The remaining values for the template arguments.

        Raises:
            KeyError: There were arguments remaining in the template.

        """
        new_template = self._add_suffix(suffix)
        new_args = self._add_kw(args)
        return new_template % new_args

    def fork(self, suffix: bytes = None, **args: _Value) -> 'RedisKey':
        """Fork a new redis key based on the current template and arguments.

        Args:
            suffix: The bytestring appended to the current template, which may
                contain new template arguments.
            args: Additional known values for the template arguments.

        """
        new_template = self._add_suffix(suffix)
        new_args = self._add_kw(args)
        return RedisKey(new_template, new_args)


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


class CleanupKeys(KeysGroup):
    """The key group for cleaning up keys that are no longer active.

    Args:
        root: The root redis key.

    """

    __slots__ = ['namespaces', 'mailboxes', 'messages', 'contents', 'roots']

    def __init__(self, root: RedisKey) -> None:
        root = root.fork(b':cleanup')
        super().__init__(root)
        self.namespaces: Final = root.end(b':ns')
        self.mailboxes: Final = root.end(b':mbx')
        self.messages: Final = root.end(b':msg')
        self.contents: Final = root.end(b':content')
        self.roots: Final = root.end(b':root')

    @property
    def keys(self) -> Sequence[bytes]:
        return [self.namespaces, self.mailboxes, self.messages, self.contents,
                self.roots]


class NamespaceKeys(KeysGroup):
    """The key group for managing mailbox namespaces, groups of mailboxes that
    typically correspond to a login user.

    Args:
        root: The root redis key.

    """

    __slots__ = ['mbx_root', 'content_root', 'mailboxes', 'max_order', 'order',
                 'uid_validity', 'subscribed', 'content_refs', 'email_ids',
                 'thread_ids']

    def __init__(self, root: RedisKey, namespace: _Value) -> None:
        root = root.fork(b':%(namespace)s', namespace=namespace)
        super().__init__(root)
        self.mbx_root: Final = root.fork(b':mbx')
        self.content_root: Final = root.fork(b':content')
        self.mailboxes: Final = root.end(b':mailboxes')
        self.max_order: Final = root.end(b':max-order')
        self.order: Final = root.end(b':order')
        self.uid_validity: Final = root.end(b':uidv')
        self.subscribed: Final = root.end(b':subscribed')
        self.content_refs: Final = root.end(b':content-refs')
        self.email_ids: Final = root.end(b':emailids')
        self.thread_ids: Final = root.end(b':threadids')

    @property
    def content_keys(self) -> RedisKey:
        """The redis key template for content keys, expecting the ``email_id``
        argument.

        """
        return self.content_root.fork(b':%(email_id)s')

    @property
    def keys(self) -> Sequence[bytes]:
        return [self.mailboxes, self.max_order, self.order, self.uid_validity,
                self.subscribed, self.content_refs, self.email_ids,
                self.thread_ids]


class MailboxKeys(KeysGroup):
    """The key group for managing a single mailbox.

    Args:
        root: The root redis key.

    """

    __slots__ = ['msg_root', 'abort', 'max_mod', 'max_uid', 'uids', 'mod_seq',
                 'seq', 'expunged', 'recent', 'deleted', 'unseen']

    def __init__(self, root: RedisKey, mailbox_id: _Value) -> None:
        root = root.fork(b':%(mailbox_id)s', mailbox_id=mailbox_id)
        super().__init__(root)
        self.msg_root: Final = root.fork(b':msg')
        self.abort: Final = root.end(b':abort')
        self.max_mod: Final = root.end(b':max-mod')
        self.max_uid: Final = root.end(b':max-uid')
        self.uids: Final = root.end(b':uids')
        self.mod_seq: Final = root.end(b':mod-seq')
        self.seq: Final = root.end(b':seq')
        self.expunged: Final = root.end(b':expunged')
        self.recent: Final = root.end(b':recent')
        self.deleted: Final = root.end(b':deleted')
        self.unseen: Final = root.end(b':unseen')

    @property
    def keys(self) -> Sequence[bytes]:
        return [self.abort, self.max_mod, self.max_uid, self.uids,
                self.mod_seq, self.seq, self.expunged, self.recent,
                self.deleted, self.unseen]


class MessageKeys(KeysGroup):
    """The key group for managing a single message, in a single mailbox.

    Args:
        root: The root redis key.

    """

    __slots__ = ['flags', 'time', 'email_id', 'thread_id']

    def __init__(self, root: RedisKey, uid: _Value) -> None:
        root = root.fork(b':%(uid)s', uid=uid)
        super().__init__(root)
        self.flags: Final = root.end(b':flags')
        self.time: Final = root.end(b':time')
        self.email_id: Final = root.end(b':emailid')
        self.thread_id: Final = root.end(b':threadid')

    @property
    def keys(self) -> Sequence[bytes]:
        return [self.flags, self.time, self.email_id, self.thread_id]
