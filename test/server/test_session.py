
import pytest

from .base import TestBase

pytestmark = pytest.mark.asyncio


class TestSession(TestBase):

    async def test_login_logout(self):
        self.login()
        self.logout()
        await self.run()

    async def test_select(self):
        self.login()
        self.select(b'INBOX', 4, 1, 104, 4)
        self.logout()
        await self.run()

    async def test_select_clears_recent(self):
        self.login()
        self.select(b'INBOX', 4, 1, 104, 4)
        self.select(b'INBOX', 4, 0, 104, 4)
        self.logout()
        await self.run()
