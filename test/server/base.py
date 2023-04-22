
import asyncio
from argparse import Namespace
from asyncio import StreamReader, StreamWriter
from collections.abc import Iterable

import pytest
from proxyprotocol.sock import SocketInfoLocal
from pysasl.hashing import BuiltinHash

from pymap.backend.dict import DictBackend
from pymap.concurrent import Event
from pymap.context import subsystem
from pymap.imap import IMAPServer
from pymap.sieve.manage import ManageSieveServer

from .mocktransport import MockTransport


class FakeArgs(Namespace):

    def __init__(self, **kwargs) -> None:
        super().__init__()
        self.__dict__.update(kwargs)

    debug = True
    demo_data = 'pymap.backend.dict'
    demo_user = 'testuser'
    demo_password = 'testpass'

    def __getattr__(self, key: str) -> None:
        return None


class TestBase:

    # For speed and determinism.
    _hash_context = BuiltinHash(hash_name='sha1', salt_len=0, rounds=1)

    @classmethod
    @pytest.fixture(autouse=True)
    def init(cls, request, backend):
        test = request.instance
        test._fd = 1
        test._matches = {}

    @pytest.fixture
    def imap_server(self, backend):
        return IMAPServer(backend.login, backend.config)

    @pytest.fixture
    def managesieve_server(self, backend):
        return ManageSieveServer(backend.login, backend.config)

    @pytest.fixture
    def args(self):
        return FakeArgs()

    @pytest.fixture
    def overrides(self):
        return {}

    @pytest.fixture
    async def backend(self, args, overrides):
        backend, config = await DictBackend.init(
            args,
            hash_context=self._hash_context,
            invalid_user_sleep=0.0,
            **overrides)
        return backend

    def _incr_fd(self):
        fd = self._fd
        self._fd += 1
        return fd

    @property
    def matches(self) -> dict[str, bytes]:
        return self._matches  # type: ignore

    def new_transport(self, server: IMAPServer | ManageSieveServer) \
            -> MockTransport:
        return MockTransport(server, self.matches, self._incr_fd())

    def new_events(self, n: int) -> Iterable[Event]:
        return (subsystem.get().new_event() for _ in range(n))

    def _check_queue(self, transport: MockTransport) -> None:
        queue = transport.queue
        assert 0 == len(queue), 'Items left on queue: ' + repr(queue)

    async def _run_transport(self, transport: MockTransport) -> None:
        server = transport.server
        reader: StreamReader = transport  # type: ignore
        writer: StreamWriter = transport  # type: ignore
        sock_info = SocketInfoLocal(transport)
        return await server(reader, writer, sock_info)

    async def run(self, *transports: MockTransport) -> None:
        failures = []
        transport_tasks = [asyncio.create_task(
            self._run_transport(transport)) for transport in transports]
        for task in transport_tasks:
            try:
                await task
            except Exception as exc:
                failures.append(exc)
        if failures:
            raise failures[0]
        for transport in transports:
            self._check_queue(transport)
