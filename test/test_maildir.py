
import pytest

from pymap.backend.maildir.layout import MaildirLayout
from pymap.backend.maildir.mailbox import Maildir, MailboxSet
from pymap.parsing.message import AppendMessage

pytestmark = pytest.mark.asyncio

_literal = (b'From: user@example.com\r\n'
            b'Subject: test\r\n'
            b'\r\n'
            b'message body\r\n')


async def test_copy_keeps_message_content(tmp_path) -> None:
    path = str(tmp_path / 'mail')
    maildir = Maildir(path, create=True)
    layout = MaildirLayout.get(path, '++', Maildir)
    mailbox_set = MailboxSet(maildir, layout)
    await mailbox_set.add_mailbox('Sent')
    inbox = await mailbox_set.get_mailbox('INBOX')
    sent = await mailbox_set.get_mailbox('Sent')
    message = await inbox.append(AppendMessage(_literal))
    dest_uid = await inbox.copy(message.uid, sent)
    assert dest_uid is not None
    message_key = message._key
    assert message_key is not None
    (key, copied), = sent._maildir.items()
    assert bytes(copied) == bytes(maildir.get_message(message_key))
    assert copied.get_payload() == 'message body\n'
