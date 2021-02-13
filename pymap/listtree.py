
from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from re import Pattern
from typing import Optional

__all__ = ['ListEntry', 'ListTree']


@dataclass(frozen=True)
class ListEntry:
    """An entry in the list results.

    Args:
        name: The name of the mailbox.
        exists: False if the mailbox should be marked ``\\Noselect``.
        marked: True, False, or None if the mailbox should be marked with
            ``\\Marked``, ``\\Unmarked`` , or neither, respectively.
        has_children: Whether the mailbox should be marked ``\\HasChildren`` or
            ``\\HasNoChildren``.

    """

    name: str
    exists: bool
    marked: Optional[bool]
    has_children: bool

    @property
    def attributes(self) -> Sequence[bytes]:
        """The mailbox attributes that should be returned with the mailbox
        in a ``LIST`` response, e.g. ``\\Noselect``.

        See Also:
            `RFC 3348 <https://tools.ietf.org/html/rfc3348>`_

        """
        ret: list[bytes] = []
        if not self.exists:
            ret.append(b'Noselect')
        if self.has_children:
            ret.append(b'HasChildren')
        else:
            ret.append(b'HasNoChildren')
        if self.marked is True:
            ret.append(b'Marked')
        elif self.marked is False:
            ret.append(b'Unmarked')
        return ret


class _TreeNode:

    __slots__ = ['parent', 'name', 'exists', 'children']

    def __init__(self, name: str, parent: _TreeNode = None) -> None:
        super().__init__()
        self.parent = parent
        self.name = name
        self.exists = False
        self.children: dict[str, _TreeNode] = {}

    def add(self, node_name: str, *extra: str) -> None:
        child = self.children.get(node_name)
        if not child:
            self.children[node_name] = child = _TreeNode(node_name, self)
        if not extra:
            child.exists = True
        else:
            child.add(*extra)


class ListTree:
    """Constructs a tree of hierarchical mailbox names. If a mailbox name
    has superior names in the heirarchy that do not exist, they are added as
    "unreferenced".

    Args:
        delimiter: The string delimiter for nested mailbox parts.

    """

    _wildcards = re.compile(r'([\*\%])')

    __slots__ = ['_delimiter', '_no_delimiter', '_root', '_marked']

    def __init__(self, delimiter: str) -> None:
        super().__init__()
        self._delimiter = delimiter
        self._no_delimiter = '[^' + re.escape(delimiter) + ']*?'
        self._root = _TreeNode('')
        self._marked: dict[str, bool] = {}

    def update(self, *names: str) -> ListTree:
        """Add all the mailbox names to the tree, filling in any missing nodes.

        Args:
            names: The names of the mailboxes.

        """
        for name in names:
            parts = name.split(self._delimiter)
            self._root.add(*parts)
        return self

    def set_marked(self, name: str, marked: bool = False,
                   unmarked: bool = False) -> None:
        """Add or remove the ``\\Marked`` and ``\\Unmarked`` mailbox
        attributes.

        Args:
            name: The name of the mailbox.
            marked: True if the ``\\Marked`` attribute should be added.
            unmarked: True if the ``\\Unmarked`` attribute should be added.

        """
        if marked:
            self._marked[name] = True
        elif unmarked:
            self._marked[name] = False
        else:
            self._marked.pop(name, None)

    def _iter(self, node: _TreeNode, name: str) -> Iterable[ListEntry]:
        if node.parent is not None:
            marked = self._marked.get(name)
            yield ListEntry(name, node.exists, marked, bool(node.children))
        for child in node.children.values():
            if name:
                child_name = self._delimiter.join((name, child.name))
            else:
                child_name = child.name
            for entry in self._iter(child, child_name):
                yield entry

    def _find(self, node: _TreeNode, node_name: str, *extra: str) -> _TreeNode:
        child = node.children[node_name]
        if extra:
            return self._find(child, *extra)
        else:
            return child

    def get(self, name: str) -> Optional[ListEntry]:
        """Return the named entry in the list tree.

        Args:
            name: The entry name.

        """
        parts = name.split(self._delimiter)
        try:
            node = self._find(self._root, *parts)
        except KeyError:
            return None
        else:
            marked = self._marked.get(name)
            return ListEntry(name, node.exists, marked, bool(node.children))

    def get_renames(self, from_name: str, to_name: str) \
            -> Sequence[tuple[str, str]]:
        """Return a list of tuples for all mailboxes that must be renamed, for
        the given rename operation. This should include
        ``(from_name, to_name)`` as well as all inferior names in the heirarchy
        that must also be renamed. If ``from_name`` does not exist, an empty
        list is returned.

        See Also:
            `RFC 3501 6.3.5
            <https://tools.ietf.org/html/rfc3501#section-6.3.5>`_

        Args:
            from_name: The original name of the mailbox.
            to_name: The intended new name of the mailbox.

        """
        from_parts = from_name.split(self._delimiter)
        try:
            from_node = self._find(self._root, *from_parts)
        except KeyError:
            return []
        from_names = (entry.name for entry in self._iter(from_node, from_name)
                      if entry.exists)
        to_names = (entry.name for entry in self._iter(from_node, to_name)
                    if entry.exists)
        return list(zip(from_names, to_names))

    def list(self) -> Iterable[ListEntry]:
        """Return all the entries in the list tree."""
        for entry in self._iter(self._root, ''):
            yield entry

    def _get_pattern(self, query: str) -> tuple[Pattern, Pattern]:
        pattern_parts: list[str] = []
        for part in self._wildcards.split(query):
            if part == '*':
                pattern_parts.append('.*?')
            elif part == '%':
                pattern_parts.append(self._no_delimiter)
            else:
                pattern_parts.append(re.escape(part))
        pattern = '^' + ''.join(pattern_parts) + '$'
        return re.compile(pattern), re.compile(pattern, re.IGNORECASE)

    def list_matching(self, ref_name: str, filter_: str) \
            -> Iterable[ListEntry]:
        """Return all the entries in the list tree that match the given query.

        Args:
            ref_name: Mailbox reference name.
            filter_: Mailbox name with possible wildcards.

        """
        canonical, canonical_i = self._get_pattern(ref_name + filter_)
        for entry in self.list():
            if entry.name == 'INBOX':
                if canonical_i.match('INBOX'):
                    yield entry
            elif canonical.match(entry.name):
                yield entry
