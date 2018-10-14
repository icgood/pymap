
import asyncio

from pysasl import SASLAuth

from pymap.demo import init
from pymap.server import IMAPServer
from pymap.state import ConnectionState
from .mocktransport import MockTransport

ConnectionState.DEFAULT_CAPABILITY = []
ConnectionState.DEFAULT_AUTH = SASLAuth([b'PLAIN'])


class TestBase:

    def setup_method(self):
        self._fd = 1
        self._run = IMAPServer(init(), None, True)
        self.matches = {}
        self.transport = self.new_transport()

    def _incr_fd(self):
        fd = self._fd
        self._fd += 1
        return fd

    def new_transport(self):
        return MockTransport(self.matches, self._incr_fd())

    @classmethod
    def new_events(cls, n=1):
        if n == 1:
            return asyncio.Event()
        else:
            return (asyncio.Event() for _ in range(n))

    async def run(self, *transports):
        coros = [self._run(self.transport, self.transport)] + \
            [self._run(transport, transport) for transport in transports]
        await asyncio.gather(*coros)
