"""send_message/send_reply kendi ürettiği Message-ID'yi döndürmeli.

'Cevap bekliyorum' takibi bu ID'yi awaiting_replies.message_id olarak
saklar; gerçek bir SMTP sunucusuna bağlanmadan doğrulamak için
_smtp_connect mock'lanır.
"""
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from app import email_client

ACCOUNT = {
    "email": "ben@example.com", "password": "gizli",
    "imap_host": "imap.example.com", "smtp_host": "smtp.example.com",
    "smtp_port": 465, "smtp_security": "ssl",
}


@contextmanager
def _fake_smtp_connect(account):
    yield MagicMock()


def test_send_message_returns_message_id_and_sets_header():
    with patch("app.email_client._smtp_connect", side_effect=_fake_smtp_connect) as connect:
        mid = email_client.send_message(ACCOUNT, "alice@example.com", "Konu", "Merhaba")

    assert mid.startswith("<") and mid.endswith(">")
    connect.assert_called_once()


def test_send_reply_returns_message_id():
    with patch("app.email_client._smtp_connect", side_effect=_fake_smtp_connect):
        mid = email_client.send_reply(
            ACCOUNT, "alice@example.com", "Konu", "Merhaba",
            in_reply_to="<orig@them>", references="",
        )

    assert mid.startswith("<") and mid.endswith(">")


def test_send_message_ids_are_unique_per_call():
    with patch("app.email_client._smtp_connect", side_effect=_fake_smtp_connect):
        mid1 = email_client.send_message(ACCOUNT, "a@example.com", "K", "B")
        mid2 = email_client.send_message(ACCOUNT, "a@example.com", "K", "B")

    assert mid1 != mid2
