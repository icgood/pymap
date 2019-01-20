
import abc
import grpclib.client  # type: ignore
from typing import Any

from .admin_pb2 import AppendRequest, AppendResponse

class AdminBase(abc.ABC):
    async def Append(self, stream: Any) -> None: ...
    def __mapping__(self): ...

class AdminStub:
    def __init__(self, channel: grpclib.client.Channel) -> None: ...
    async def Append(self, request: AppendRequest) -> AppendResponse: ...
