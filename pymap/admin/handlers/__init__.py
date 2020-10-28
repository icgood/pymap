
from __future__ import annotations

from abc import abstractmethod, ABCMeta
from contextlib import closing, asynccontextmanager, AsyncExitStack
from typing import Any, Type, Optional, Mapping, Dict, AsyncGenerator
from typing_extensions import Final

from pymap.context import connection_exit
from pymap.exceptions import InvalidAuth, ResponseError
from pymap.interfaces.backend import BackendInterface
from pymap.interfaces.login import IdentityInterface
from pymap.interfaces.session import SessionInterface
from pymap.plugin import Plugin
from pymapadmin.grpc.admin_pb2 import Result, SUCCESS, FAILURE
from pysasl import AuthenticationCredentials

from ..errors import get_unimplemented_error
from ..token import TokenCredentials

__all__ = ['handlers', 'BaseHandler', 'LoginHandler']

#: Registers new admin handler plugins.
handlers: Plugin[Type[BaseHandler]] = Plugin('pymap.admin.handlers')


class BaseHandler(metaclass=ABCMeta):
    """Base class for implementing admin request handlers.

    Args:
        backend: The backend in use by the system.
        admin_token: The admin token string that can authenticate any admin
            operation.

    """

    def __init__(self, backend: BackendInterface,
                 admin_token: Optional[bytes]) -> None:
        super().__init__()
        self.config: Final = backend.config
        self.login: Final = backend.login
        self.admin_token: Final = admin_token

    @abstractmethod
    def __mapping__(self) -> Dict[str, Any]:
        # Remove if IServable becomes public API in grpclib
        ...

    @asynccontextmanager
    async def catch_errors(self, command: str) -> AsyncGenerator[Result, None]:
        """Context manager to catch
        :class:`~pymap.exceptions.ResponseError` exceptions and include them in
        the response.

        Args:
            command: The admin command name.

        """
        response = b'. OK %b completed.' % command.encode('utf-8')
        result = Result(code=SUCCESS, response=response)
        async with AsyncExitStack() as stack:
            connection_exit.set(stack)
            try:
                yield result
            except NotImplementedError as exc:
                raise get_unimplemented_error() from exc
            except ResponseError as exc:
                result.code = FAILURE
                result.response = bytes(exc.get_response(b'.'))
                result.key = type(exc).__name__

    @asynccontextmanager
    async def login_as(self, metadata: Mapping[str, str], user: str) \
            -> AsyncGenerator[IdentityInterface, None]:
        """Context manager to login an identity object.

        Args:
            stream: The grpc request/response stream.
            user: The user to authorize as.

        Raises:
            :class:`~pymap.exceptions.InvalidAuth`

        """
        try:
            creds: AuthenticationCredentials = TokenCredentials(
                metadata['auth-token'], self.admin_token, user)
        except (KeyError, ValueError) as exc:
            raise InvalidAuth() from exc
        yield await self.login.authenticate(creds)

    @asynccontextmanager
    async def with_session(self, identity: IdentityInterface) \
            -> AsyncGenerator[SessionInterface, None]:
        """Context manager to create a mail session for the identity.

        Args:
            identity: The authenticated user identity.

        Raises:
            :class:`~pymap.exceptions.InvalidAuth`

        """
        stack = connection_exit.get()
        session = await stack.enter_async_context(identity.new_session())
        stack.enter_context(closing(session))
        yield session
