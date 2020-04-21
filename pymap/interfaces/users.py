
from __future__ import annotations

from abc import abstractmethod
from typing import Optional, AsyncIterable
from typing_extensions import Protocol

from ..user import UserMetadata

__all__ = ['UsersInterface']


class UsersInterface(Protocol):
    """Defines admin functions that backends can implement to manage users."""

    @abstractmethod
    def list_users(self, *, match: str = None) -> AsyncIterable[str]:
        """Iterate all matching users. The format *match* argument depends on
        the backend implementation.

        Args:
            match: A filter string for matched users.

        """
        ...

    @abstractmethod
    async def get_user(self, user: str) -> Optional[UserMetadata]:
        """Return the password and other metadata for a username.

        Args:
            user: The user login string.

        """
        ...

    @abstractmethod
    async def set_user(self, user: str, data: UserMetadata) -> None:
        """Assign a password and other metadata to a username, creating it if
        it does not exist.

        Args:
            user: The user login string.
            data: The user metadata, including password.

        Raises:
            :class:`~pymap.exceptions.UserConflict`

        """
        ...

    @abstractmethod
    async def delete_user(self, user: str) -> None:
        """Delete a user and all mail data associated with it.

        Args:
            user: The user login string.

        Raises:
            :class:`~pymap.exceptions.UserNotFound`

        """
        ...
