
from __future__ import annotations

from abc import abstractmethod, ABCMeta
from contextlib import closing, asynccontextmanager, AsyncExitStack
from typing import Any, Type, Dict, AsyncGenerator
from typing_extensions import Final

from pymap.context import connection_exit
from pymap.exceptions import ResponseError
from pymap.interfaces.backend import BackendInterface
from pymap.interfaces.session import SessionInterface
from pymap.plugin import Plugin
from pymapadmin.grpc.admin_pb2 import Login, Result, SUCCESS, FAILURE
from pysasl import AuthenticationCredentials
from pysasl.external import ExternalResult

__all__ = ['handlers', 'BaseHandler', 'LoginHandler']

#: Registers new admin handler plugins.
handlers: Plugin[Type[BaseHandler]] = Plugin('pymap.admin.handlers')


class BaseHandler(metaclass=ABCMeta):
    """Base class for implementing admin request handlers.

    Args:
        backend: The backend in use by the system.
        public: True if the requests are received from a public-facing client.

    """

    def __init__(self, backend: BackendInterface, public: bool) -> None:
        super().__init__()
        self.config: Final = backend.config
        self.login: Final = backend.login
        self.public: Final = public

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
        try:
            yield result
        except ResponseError as exc:
            result.code = FAILURE
            result.response = bytes(exc.get_response(b'.'))
            result.key = type(exc).__name__


class LoginHandler(BaseHandler, metaclass=ABCMeta):
    """Base class for implementing admin request handlers that login as a user
    to handle requests.

    Args:
        backend: The backend in use by the system.

    """

    @asynccontextmanager
    async def login_as(self, login: Login) \
            -> AsyncGenerator[SessionInterface, None]:
        """Context manager to login as a user and provide a session object.

        Args:
            login: Holds the auuthentication credentials from the request.

        Raises:
            :class:`~pymap.exceptions.InvalidAuth`

        """
        if self.public:
            creds = AuthenticationCredentials(
                login.authcid, login.secret, login.authzid or None)
        else:
            creds = ExternalResult(login.authzid or None)
        async with AsyncExitStack() as stack:
            connection_exit.set(stack)
            session = await stack.enter_async_context(self.login(creds))
            stack.enter_context(closing(session))
            yield session
