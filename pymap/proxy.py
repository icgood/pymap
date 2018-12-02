
import asyncio
import threading
from contextvars import copy_context
from concurrent.futures import Executor
from functools import partial
from typing import cast, Optional

from .interfaces.session import LoginProtocol, SessionInterface

__all__ = ['ExecutorProxy']


class ExecutorProxy:
    """Proxies calls to :class:`~pymap.interfaces.session.SessionInterface`
    object or :class:`~pymap.interfaces.session.LoginProtocol`
    functions through an :class:`~concurrent.futures.Executor`.

    Args:
        executor: The executor to proxy through, e.g. a thread pool, or None.

    """

    def __init__(self, executor: Optional[Executor]) -> None:
        super().__init__()
        self.executor = executor
        self._local = _EventLoopLocal() if executor else None

    def wrap_login(self, login: LoginProtocol) -> LoginProtocol:
        """Wrap a login function so that it is called inside the executor."""
        if self.executor is None:
            return login
        else:
            wrapped = partial(self._call, login)
            return cast(LoginProtocol, wrapped)

    def wrap_session(self, session: SessionInterface) -> SessionInterface:
        """Wrap a session object so that all its methods are called inside the
        executor.

        """
        if self.executor is None:
            return session
        else:
            wrapped = _ProxyWrapper(self._call, session)
            return cast(SessionInterface, wrapped)

    async def _call(self, func, *args, **kwargs):
        loop = asyncio.get_event_loop()
        ctx = copy_context()
        func_call = partial(func, *args, **kwargs)
        return await loop.run_in_executor(
            self.executor, self._call_with_event_loop, func_call(), ctx)

    def _call_with_event_loop(self, future, ctx):
        loop = self._local.event_loop
        return ctx.run(loop.run_until_complete, future)


class _EventLoopLocal(threading.local):

    def __init__(self) -> None:
        self.event_loop = asyncio.new_event_loop()


class _ProxyWrapper:

    def __init__(self, call, obj) -> None:
        super().__init__()
        self._call = call
        self._obj = obj

    def __getattr__(self, key: str):
        func = getattr(self._obj, key)
        return partial(self._call, func)
