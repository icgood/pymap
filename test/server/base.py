
import asyncio
from argparse import Namespace
from typing import Dict

import pytest  # type: ignore

from pymap.backend.dict import DictBackend
from pymap.context import subsystem
from pymap.imap import IMAPServer
from pymap.sieve.manage import ManageSieveServer

from .mocktransport import MockTransport


class FakeArgs(Namespace):
    debug = True
    insecure_login = True
    demo_data = 'pymap.backend.dict'
    demo_user = 'testuser'
    demo_password = 'testpass'

    def __getattr__(self, key: str) -> None:
        return None


class TestBase:

    @classmethod
    @pytest.fixture(autouse=True)
    def init(cls, request, backend):
        test = request.instance
        test._fd = 1
        test.matches: Dict[str, bytes] = {}

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
    async def backend(self, args):
        backend, config = await DictBackend.init(args)
        config.disable_search_keys = [b'DRAFT']
        return backend

    def _incr_fd(self):
        fd = self._fd
        self._fd += 1
        return fd

    def new_transport(self, server):
        return MockTransport(server, self.matches, self._incr_fd())

    def new_events(self, n=1):
        if n == 1:
            return subsystem.get().new_event()
        else:
            return (subsystem.get().new_event() for _ in range(n))

    def _check_queue(self, transport):
        queue = transport.queue
        assert 0 == len(queue), 'Items left on queue: ' + repr(queue)

    async def _run_transport(self, transport):
        server = transport.server
        return await server(transport, transport)

    async def run(self, *transports):
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
