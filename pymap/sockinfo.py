
from asyncio import BaseTransport, StreamWriter
from typing import Any, Union, Optional, Tuple, Mapping

__all__ = ['SocketInfo']

_Transport = Union[BaseTransport, StreamWriter]
_PeerName = Union[Tuple[str, int], Tuple[str, int, int, int], str]
_PeerCert = Mapping[str, Any]  # {'issuer': ..., ...}


class SocketInfo:
    """Information about a connected socket, which may be useful for
    server-side logic such as authentication and authorization.

    See Also:
        :meth:`~asyncio.BaseTransport.get_extra_info`

    """

    def __init__(self, transport: _Transport) -> None:
        super().__init__()
        self._transport = transport

    @property
    def peername(self) -> _PeerName:
        peername = self._transport.get_extra_info('peername')
        if peername is None:
            raise ValueError('peername')
        return peername

    @property
    def peercert(self) -> Optional[_PeerCert]:
        return self._transport.get_extra_info('peercert')

    def __getattr__(self, name: str) -> Any:
        return self._transport.get_extra_info(name)

    def __str__(self) -> str:
        return '<SocketInfo peername=%r sockname=%r peercert=%r>' \
            % (self.peername, self.sockname, self.peercert)

    def __bytes__(self) -> bytes:
        return bytes(str(self), 'utf-8')
