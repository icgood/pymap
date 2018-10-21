
import pytest  # type: ignore

from .base import TestBase

pytestmark = pytest.mark.asyncio


class TestCopy(TestBase):

    async def test_copy(self):
        self.transport.push_login()
        self.transport.push_select(b'INBOX')
        self.transport.push_readline(
            b'copy1 COPY 1:* Trash\r\n')
        self.transport.push_write(
            b'copy1 OK [COPYUID ', (br'\d+', ), b' 100:103 100:103]'
            b' COPY completed.\r\n')
        self.transport.push_select(b'Trash', 4, 4)
        self.transport.push_logout()
        await self.run()

    async def test_uid_copy(self):
        self.transport.push_login()
        self.transport.push_select(b'INBOX')
        self.transport.push_readline(
            b'copy1 UID COPY 1:* Trash\r\n')
        self.transport.push_write(
            b'copy1 OK [COPYUID ', (br'\d+', ), b' 100:103 100:103]'
            b' COPY completed.\r\n')
        self.transport.push_select(b'Trash', 4, 4)
        self.transport.push_logout()
        await self.run()
