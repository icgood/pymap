
import asyncio
from argparse import Namespace
from typing import Dict

from pymap.backend.dict import DictBackend
from .mocktransport import MockTransport


class TestBase:

    class FakeArgs(Namespace):
        debug = True
        insecure_login = True
        demo_data = True
        demo_user = 'testuser'
        demo_password = 'testpass'

    def setup_method(self) -> None:
        self._fd = 1
        loop = asyncio.get_event_loop()
        self._run = server = loop.run_until_complete(
                DictBackend.init(self.FakeArgs()))
        self.config = server.config
        self.matches: Dict[str, bytes] = {}
        self.transport = self.new_transport()

    def _incr_fd(self):
        fd = self._fd
        self._fd += 1
        return fd

    def new_transport(self):
        return MockTransport(self.matches, self._incr_fd())

    def new_events(self, n=1):
        if n == 1:
            return self.config.new_event()
        else:
            return (self.config.new_event() for _ in range(n))

    async def run(self, *transports):
        coros = [self._run(self.transport, self.transport)] + \
            [self._run(transport, transport) for transport in transports]
        await asyncio.gather(*coros)
