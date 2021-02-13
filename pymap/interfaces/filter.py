
from __future__ import annotations

from abc import abstractmethod
from collections.abc import Sequence
from typing import TypeVar, Optional, Protocol

from ..parsing.message import AppendMessage

__all__ = ['FilterValueT', 'FilterInterface',
           'FilterCompilerInterface', 'FilterSetInterface']

#: Type variable for the filter value representation.
FilterValueT = TypeVar('FilterValueT')


class FilterInterface(Protocol):
    """Protocol defining the interface for message filters. Filters may choose
    the mailbox or discard the message or modify its contents or metadata. The
    filter may also trigger external functionality, such as sending a vacation
    auto-response or a copy of the message to an SMTP endpoint.

    """

    __slots__: Sequence[str] = []

    @abstractmethod
    async def apply(self, sender: str, recipient: str, mailbox: str,
                    append_msg: AppendMessage) \
            -> tuple[Optional[str], AppendMessage]:
        """Run the filter and return the mailbox where it should be appended,
        or None to discard, and the message to be appended, which is usually
        the same as ``append_msg``.

        Args:
            sender: The envelope sender of the message.
            recipient: The envelope recipient of the message.
            mailbox: The intended mailbox to append the message.
            append_msg: The message to be appended.

        Raises:
            :exc:`~pymap.exceptions.AppendFailure`

        """
        ...


class FilterCompilerInterface(Protocol[FilterValueT]):
    """Protocol for classes which can compile a filter value into an
    implementation.

    """

    __slots__: Sequence[str] = []

    @property
    @abstractmethod
    def value_type(self) -> type[FilterValueT]:
        """The filter value type."""
        ...

    @property
    @abstractmethod
    def filter_type(self) -> type[FilterInterface]:
        """The filter implementation type."""
        ...

    @abstractmethod
    async def compile(self, value: FilterValueT) -> FilterInterface:
        """Compile the filter value and return the resulting implementation.

        Args:
            value: The filter value:

        """
        ...


class FilterSetInterface(Protocol[FilterValueT]):
    """Protocol defining the interface for accessing and managing the set of
    message filters currently active and available. This interface
    intentionally resembles that of a ManageSieve server.

    See Also:
        `RFC 5804 <https://tools.ietf.org/html/rfc5804>`_

    """

    __slots__: Sequence[str] = []

    @property
    @abstractmethod
    def compiler(self) -> FilterCompilerInterface[FilterValueT]:
        """Compiles filter values into an implementation."""
        ...

    @abstractmethod
    async def put(self, name: str, value: FilterValueT) -> None:
        """Add or update the named filter value.

        Args:
            name: The filter name.
            value: The filter value.

        """
        ...

    @abstractmethod
    async def delete(self, name: str) -> None:
        """Delete the named filter. If the named filter is active,
        :class:`ValueError` is raised.

        Args:
            name: The filter name.

        Raises:
            :class:`KeyError`, :class:`ValueError`

        """
        ...

    @abstractmethod
    async def rename(self, before_name: str, after_name: str) -> None:
        """Rename the filter, maintaining its active status. An exception is
        raised if ``before_name`` does not exist or ``after_name`` already
        exists.

        Args:
            before_name: The current filter name.
            after_name: The intended filter name.

        Raises:
            :class:`KeyError`

        """
        ...

    @abstractmethod
    async def clear_active(self) -> None:
        """Disable any active filters."""
        ...

    @abstractmethod
    async def set_active(self, name: str) -> None:
        """Set the named filter to be active.

        Args:
            name: The filter name.

        Raises:
            :class:`KeyError`

        """

    @abstractmethod
    async def get(self, name: str) -> FilterValueT:
        """Return the named filter value.

        Args:
            name: The filter name.

        Raises:
            :class:`KeyError`

        """
        ...

    @abstractmethod
    async def get_active(self) -> Optional[FilterValueT]:
        """Return the active filter value, if any."""
        ...

    @abstractmethod
    async def get_all(self) -> tuple[Optional[str], Sequence[str]]:
        """Return the active filter name and a list of all filter names."""
        ...
