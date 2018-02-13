
import pytest

from .base import TestBase

pytestmark = pytest.mark.asyncio


class TestCopy(TestBase):

    async def test_copy(self):
        self.transport.push_login()
        self.transport.push_select(b'INBOX', 4, 1, 104, 4)
        self.transport.push_readline(
            b'copy1 COPY 1:* Trash\r\n')
        self.transport.push_write(
            b'copy1 OK COPY completed.\r\n')
        self.transport.push_select(b'Trash', 4, 4, 104, 4)
        self.transport.push_logout()
        await self.run()

    async def test_uid_copy(self):
        self.transport.push_login()
        self.transport.push_select(b'INBOX', 4, 1, 104, 4)
        self.transport.push_readline(
            b'copy1 UID COPY 1:* Trash\r\n')
        self.transport.push_write(
            b'copy1 OK COPY completed.\r\n')
        self.transport.push_select(b'Trash', 4, 4, 104, 4)
        self.transport.push_logout()
        await self.run()
