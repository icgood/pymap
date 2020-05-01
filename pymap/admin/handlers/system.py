
from __future__ import annotations

from grpclib.server import Stream
from pymap import __version__ as server_version
from pymapadmin.grpc.admin_grpc import SystemBase
from pymapadmin.grpc.admin_pb2 import PingRequest, PingResponse

from . import BaseHandler

__all__ = ['SystemHandlers']

_PingStream = Stream[PingRequest, PingResponse]


class SystemHandlers(SystemBase, BaseHandler):
    """The GRPC handlers, executed when an admin request is received. Each
    handler should receive a request, take action, and send the response.

    See Also:
        :class:`grpclib.server.Server`

    """

    async def Ping(self, stream: _PingStream) -> None:
        """Respond to a ping request. For example::

            $ pymap-admin ping

        See ``pymap-admin ping --help`` for more options.

        Args:
            stream (:class:`~grpclib.server.Stream`): The stream for the
                request and response.

        """
        request = await stream.recv_message()
        assert request is not None
        resp = PingResponse(server_version=server_version,
                            public_client=self.public)
        await stream.send_message(resp)
