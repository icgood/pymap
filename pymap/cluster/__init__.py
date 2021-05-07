
from __future__ import annotations

from abc import abstractmethod
from collections.abc import Collection, Iterator, Mapping, MutableMapping, \
    MutableSet, Set
from typing import TypeVar, Protocol, Any
from weakref import WeakKeyDictionary, WeakSet, WeakValueDictionary

__all__ = ['MemberInterface', 'ListenCallback', 'ClusterMetadata']

ArgT = TypeVar('ArgT')
ArgT_contra = TypeVar('ArgT_contra', contravariant=True)


class MemberInterface(Protocol):
    """A hashable type that represents a cluster member node."""

    @abstractmethod
    def __hash__(self) -> int:
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """The name of the cluster member node."""
        ...

    @property
    @abstractmethod
    def metadata(self) -> _Metadata:
        """The metadata mapping from the cluster member node."""
        ...


_Metadata = Mapping[str, bytes]
_MemberValues = WeakKeyDictionary[MemberInterface, bytes]
_MemberValuesView = Mapping[MemberInterface, bytes]


class ListenCallback(Protocol[ArgT_contra]):

    @abstractmethod
    def __call__(self, arg: ArgT_contra, /, metadata: _Metadata) -> None:
        """Called when the value associated with a local metadata key has been
        changed.

        Args:
            arg: The argument given when the callback was registered with
                :meth:`~ClusterMetadata.listen`.
            metadata: The updated local metadata mapping.

        """
        ...


class _LocalMetadata(MutableMapping[str, bytes]):

    def __init__(self) -> None:
        super().__init__()
        self._map: dict[str, bytes] = {}
        self._callbacks: WeakValueDictionary[ListenCallback[Any], object] = \
            WeakValueDictionary()

    def __getitem__(self, key: str) -> bytes:
        return self._map[key]

    def __setitem__(self, key: str, value: bytes) -> None:
        local = self._map
        curr = local.get(key)
        if curr != value:
            local[key] = value
            for callback, arg in self._callbacks.items():
                callback(arg, local)

    def __delitem__(self, key: str) -> None:
        local = self._map
        del local[key]
        for callback, arg in self._callbacks.items():
            callback(arg, local)

    def __iter__(self) -> Iterator[str]:
        return iter(self._map)

    def __len__(self) -> int:
        return len(self._map)

    def __repr__(self) -> str:  # pragma: no cover
        return repr(self._map)


class _RemoteMetadata(Mapping[str, _MemberValues]):

    def __init__(self) -> None:
        super().__init__()
        self._map: dict[str, _MemberValues] = {}

    def __getitem__(self, key: str) -> _MemberValues:
        return self._map[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._map)

    def __len__(self) -> int:
        return len(self._map)

    def _add_member(self, member: MemberInterface) -> None:
        for key, value in member.metadata.items():
            member_values = self._map.get(key)
            if member_values is None:
                self._map[key] = member_values = WeakKeyDictionary()
            member_values[member] = value

    def _del_member(self, member: MemberInterface) -> None:
        for member_values in self._map.values():
            member_values.pop(member, None)

    def __repr__(self) -> str:  # pragma: no cover
        return repr({key: dict(val) for key, val in self._map.items()})


class ClusterMetadata(MutableSet[MemberInterface]):
    """Keeps a mapping of metadata pertaining to the current instance and
    possibly other clustered instances, if the current instance is part of a
    cluster.

    The object also acts as a set of :class:`MemberInterface` objects. The
    cluster service should add new or updated members and discard them as they
    go offline.

    Args:
        init: Initial remote cluster members.

    """

    def __init__(self, init: Collection[MemberInterface] = [], /) -> None:
        super().__init__()
        self._members: WeakSet[MemberInterface] = WeakSet()
        self._local = _LocalMetadata()
        self._remote = _RemoteMetadata()
        for member in init:
            self.add(member)

    def __contains__(self, member: object) -> bool:
        return member in self._members

    def __iter__(self) -> Iterator[MemberInterface]:
        return iter(self._members)

    def __len__(self) -> int:
        return len(self._members)

    def add(self, member: MemberInterface) -> None:
        self._members.add(member)
        self._remote._add_member(member)

    def discard(self, member: MemberInterface) -> None:
        self._members.discard(member)
        self._remote._del_member(member)

    @property
    def local(self) -> MutableMapping[str, bytes]:
        """The local cluster instance metadata. Keys added, removed, and
        modified in this mapping should be disseminated to the rest of the
        cluster.

        """
        return self._local

    @property
    def remote(self) -> Mapping[str, _MemberValuesView]:
        """The remote cluster instance metadata, organized by metadata key."""
        return self._remote

    def get_all(self, key: str) -> Set[bytes]:
        """Returns the set of all known values for the metadata key, local and
        remote.

        Args:
            key: The metadata key.

        """
        results = set(self._remote[key].values())
        if key in self._local:
            results.add(self._local[key])
        return results

    def listen(self, callback: ListenCallback[ArgT], arg: ArgT) -> None:
        """Adds a callback to be run whenever the local metadata has been
        modified. Cluster services can use this to disseminate metadata
        changes.

        Note:
            The *arg* object is weakly referenced, and the callback will be
            automatically removed if it is :term:`garbage-collected <garbage
            collection>`.

        Args:
            callback: Function called with the updated local metadata mapping.
            arg: The first argument passed to *callback*.

        """
        self._local._callbacks[callback] = arg
        callback(arg, self._local)
