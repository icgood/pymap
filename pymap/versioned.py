
from __future__ import annotations

from abc import abstractmethod, ABCMeta
from collections.abc import Sequence
from typing import Any, ClassVar, Generic, TypeVar

__all__ = ['VersionedT', 'EntityTagT', 'Versioned']

#: Type variable for versioned object entity tags.
EntityTagT = TypeVar('EntityTagT')

#: Type variable for versioned objects.
VersionedT = TypeVar('VersionedT', bound='Versioned[Any]')


class Versioned(Generic[EntityTagT], metaclass=ABCMeta):
    """This simple base class defines objects that supports "versioning" using
    entity tags.

    The :attr:`.entity_tag` of an object represents the *current* object and
    :attr:`.previous_entity_tag` represents the object that it is intended to
    replace. A versioned object then provides optimistic locking by preventing
    replacement of an object other than the one it was intended to replace.

    In a linear chain of objects and their replacements, the first object in
    the chain should have a :attr:`.previous_entity_tag` of ``None``, and every
    subsequent object should have a :attr:`.previous_entity_tag` equal to the
    :attr:`.entity_tag` of the object before it.

    """

    __slots__: Sequence[str] = []

    #: A special marker for :attr:`.previous_entity_tag` indicating that any
    #: previous object may be replaced.
    REPLACE_ANY: ClassVar[Any] = object()

    @property
    @abstractmethod
    def entity_tag(self) -> EntityTagT:
        """Represents the *current* version of the object."""
        ...

    @property
    @abstractmethod
    def previous_entity_tag(self) -> EntityTagT | None:
        """Represents the version of the object it is intended to replace."""
        ...

    def can_replace(self: VersionedT, previous: VersionedT | None) -> bool:
        """Check if this object can replace the *previous* object.

        Args:
            previous: The object to be replaced, if any.

        """
        previous_entity_tag = self.previous_entity_tag
        if previous_entity_tag is self.REPLACE_ANY:
            return True
        elif previous is None:
            return previous_entity_tag is None
        else:
            return bool(previous_entity_tag == previous.entity_tag)

    @classmethod
    @abstractmethod
    def new_entity_tag(cls) -> EntityTagT:
        """Generate a new random value for :attr:`.entity_tag`."""
        ...
