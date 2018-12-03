
import re
from collections import OrderedDict
from typing import Dict, Iterable, Sequence, List, NamedTuple

__all__ = ['ListEntry', 'ListTree']


class ListEntry(NamedTuple):
    """An entry in the list results.

    Attributes:
        name: The name of the mailbox.
        exists: False if the mailbox should be marked ``\\Noselect``.
        has_children: Whether the mailbox should be marked ``\\HasChildren`` or
            ``\\HasNoChildren``.

    """

    name: str
    exists: bool
    has_children: bool

    @property
    def attributes(self) -> Sequence[bytes]:
        """The mailbox attributes that should be returned with the mailbox
        in a ``LIST`` response, e.g. ``\\Noselect``.

        See Also:
            `RFC 3348 <https://tools.ietf.org/html/rfc3348>`_

        """
        ret: List[bytes] = []
        if not self.exists:
            ret.append(b'Noselect')
        if self.has_children:
            ret.append(b'HasChildren')
        else:
            ret.append(b'HasNoChildren')
        return ret


class _TreeNode:

    __slots__ = ['parent', 'name', 'exists', 'children']

    def __init__(self, name: str, parent: '_TreeNode' = None) -> None:
        super().__init__()
        self.parent = parent
        self.name = name
        self.exists = False
        self.children: Dict[str, '_TreeNode'] = OrderedDict()

    def add(self, node_name: str, *extra: str) -> None:
        child = self.children.get(node_name)
        if not child:
            self.children[node_name] = child = _TreeNode(node_name, self)
        if not extra:
            child.exists = True
        else:
            child.add(*extra)

    def flatten(self, delimiter: str) -> str:
        node = self
        parts: List[str] = []
        while node.parent is not None:
            parts.append(node.name)
            node = node.parent
        return delimiter.join(reversed(parts))


class ListTree:
    """Constructs a tree of hierarchical mailbox names. If a mailbox name
    has superior names in the heirarchy that do not exist, they are added as
    "unreferenced".

    Args:
        delimiter: The string delimiter for nested mailbox parts.

    """

    _asterisk_escape = re.escape('*')
    _percent_escape = re.escape('%')
    _anything = '.*?'

    __slots__ = ['_delimiter', '_no_delimiter', '_root']

    def __init__(self, delimiter: str) -> None:
        super().__init__()
        self._delimiter = delimiter
        self._no_delimiter = '[^' + re.escape(delimiter) + ']*?'
        self._root = _TreeNode('')

    def update(self, *names: str) -> 'ListTree':
        """Add all the mailbox names to the tree, filling in any missing nodes.

        Args:
            names: The names of the mailboxes.

        """
        for name in names:
            parts = name.split(self._delimiter)
            self._root.add(*parts)
        return self

    def _iter(self, node: _TreeNode) -> Iterable[ListEntry]:
        if node.parent is not None:
            name = node.flatten(self._delimiter)
            yield ListEntry(name, node.exists, bool(node.children))
        for child in node.children.values():
            for entry in self._iter(child):
                yield entry

    def list(self) -> Iterable[ListEntry]:
        """Return all the entries in the list tree."""
        for entry in self._iter(self._root):
            yield entry

    def list_matching(self, ref_name: str, filter_: str) \
            -> Iterable[ListEntry]:
        """Return all the entries in the list tree that match the given query.

        Args:
            ref_name: Mailbox reference name.
            filter_: Mailbox name with possible wildcards.

        """
        re_interpreted = '^' + re.escape(ref_name + filter_) + '$'
        re_interpreted = re_interpreted.replace(
            self._asterisk_escape, self._anything)
        re_interpreted = re_interpreted.replace(
            self._percent_escape, self._no_delimiter)
        compiled_canonical = re.compile(re_interpreted)
        for entry in self.list():
            if entry.name == 'INBOX':
                if re.match(re_interpreted, 'INBOX', re.IGNORECASE):
                    yield entry
            elif compiled_canonical.match(entry.name):
                yield entry
