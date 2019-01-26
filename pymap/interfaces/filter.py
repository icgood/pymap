
from abc import abstractmethod
from typing import Optional, Tuple, Mapping
from typing_extensions import Protocol

from .message import AppendMessage

__all__ = ['FilterInterface', 'FilterSetInterface']


class FilterInterface(Protocol):
    """Protocol defining the interface for message filters. Filters may choose
    the mailbox or discard the message or modify its contents or metadata. The
    filter may also trigger external functionality, such as sending a vacation
    auto-response or a copy of the message to an SMTP endpoint.

    """

    @abstractmethod
    async def apply(self, sender: str, recipient: str, mailbox: str,
                    append_msg: AppendMessage) \
            -> Tuple[Optional[str], AppendMessage]:
        """Run the filter and return the mailbox where it should be appended,
        or None to discard, and the message to be appended, which is usually
        the same as ``append_msg``.

        Args:
            sender: The envelope sender of the message.
            recipient: The envelope recipient of the message.
            mailbox: The intended mailbox to append the message.
            append_msg: The message to be appended.

        raises:
            :exc:`~pymap.exceptions.AppendFailure`

        """
        ...


class FilterSetInterface(Protocol):
    """Protocol defining the interface for accessing and managing the set of
    message filters currently active and available. This interface
    intentionally resembles that of a ManageSieve server.

    See Also:
        `RFC 5804 <https://tools.ietf.org/html/rfc5804>`_

    """

    @abstractmethod
    async def put(self, name: str, value: FilterInterface,
                  check: bool = False) -> None:
        """Add or update the named filter implementation.

        Args:
            name: The filter name.
            value: The filter value.
            check: Do not add or update the filter, but throw any errors that
                would have occurred.

        """
        ...

    @abstractmethod
    async def delete(self, name: str) -> None:
        """Delete the named filter.

        Args:
            name: The filter name.

        Raises:
            :class:`KeyError`

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
    async def set_active(self, name: Optional[str]) -> None:
        """Set the named filter to be active, or disable any active filters if
        ``name`` is None.

        Args:
            name: The filter name.

        """

    @abstractmethod
    async def get(self, name: str) -> FilterInterface:
        """Return the named filter implementation.

        Args:
            name: The filter name.

        Raises:
            :class:`KeyError`

        """
        ...

    @abstractmethod
    async def get_active(self) -> Optional[FilterInterface]:
        """Return the active filter implementation, if any."""
        ...

    @abstractmethod
    async def get_all(self) \
            -> Tuple[Optional[str], Mapping[str, FilterInterface]]:
        """Return the active filter name and a mapping of filter names to
        implementation.

        """
        ...
