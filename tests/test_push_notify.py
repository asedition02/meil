"""Web Push bildirim testleri (app/push_notify.py)."""
import base64
from unittest.mock import patch

from pywebpush import WebPushException

from app import database, push_notify


def _add_sub(endpoint="https://push.example.com/abc"):
    database.save_push_subscription(endpoint, p256dh="p256dh-key", auth="auth-key")


class _FakeResponse:
    def __init__(self, status_code):
        self.status_code = status_code


def test_vapid_keypair_generated_and_persisted(tmp_db):
    assert database.get_setting("vapid_private_key") is None

    private1, public1 = push_notify.get_or_create_vapid_keypair()
    assert private1 and public1

    # Ham baytların uzunluğu doğru mu (private=32, public=uncompressed point=65)
    def _b64url_len(s):
        pad = "=" * ((4 - len(s) % 4) % 4)
        return len(base64.urlsafe_b64decode(s + pad))

    assert _b64url_len(private1) == 32
    assert _b64url_len(public1) == 65

    # İkinci çağrı yeni anahtar üretmemeli — DB'den okumalı
    private2, public2 = push_notify.get_or_create_vapid_keypair()
    assert (private1, public1) == (private2, public2)
    assert push_notify.vapid_public_key() == public1


def test_send_push_with_no_subscriptions_does_nothing(tmp_db):
    with patch("app.push_notify.webpush") as wp:
        sent = push_notify.send_push("Başlık", "Gövde")
    assert sent == 0
    wp.assert_not_called()
    # Abonelik yoksa VAPID anahtarı bile üretilmemeli
    assert database.get_setting("vapid_private_key") is None


def test_send_push_sends_to_all_subscriptions(tmp_db):
    _add_sub("https://push.example.com/one")
    _add_sub("https://push.example.com/two")

    with patch("app.push_notify.webpush") as wp:
        sent = push_notify.send_push("Hatırlatma", "Zamanı geldi")

    assert sent == 2
    assert wp.call_count == 2
    kwargs = wp.call_args.kwargs
    assert kwargs["vapid_claims"]["sub"].startswith("mailto:")
    assert "Hatırlatma" in kwargs["data"]


def test_send_push_removes_subscription_on_410(tmp_db):
    _add_sub("https://push.example.com/gone")
    assert len(database.list_push_subscriptions()) == 1

    with patch("app.push_notify.webpush",
               side_effect=WebPushException("gone", response=_FakeResponse(410))):
        sent = push_notify.send_push("Başlık", "Gövde")

    assert sent == 0
    assert database.list_push_subscriptions() == []


def test_send_push_keeps_subscription_on_other_errors(tmp_db):
    _add_sub("https://push.example.com/temp-fail")

    with patch("app.push_notify.webpush",
               side_effect=WebPushException("server error", response=_FakeResponse(500))):
        sent = push_notify.send_push("Başlık", "Gövde")

    assert sent == 0
    assert len(database.list_push_subscriptions()) == 1


def test_vapid_subject_defaults_to_first_account_email(tmp_db):
    assert push_notify._vapid_subject() == "mailto:admin@meil.local"
    database.create_account({
        "email": "ben@example.com", "password": "gizli",
        "imap_host": "imap.example.com", "smtp_host": "smtp.example.com",
    })
    assert push_notify._vapid_subject() == "mailto:ben@example.com"


def test_database_save_list_delete_push_subscription(tmp_db):
    assert database.list_push_subscriptions() == []
    database.save_push_subscription("https://push.example.com/x", "p", "a")
    subs = database.list_push_subscriptions()
    assert len(subs) == 1
    assert subs[0]["endpoint"] == "https://push.example.com/x"

    # Aynı endpoint tekrar kaydedilirse günceller, çoğaltmaz
    database.save_push_subscription("https://push.example.com/x", "p2", "a2")
    subs = database.list_push_subscriptions()
    assert len(subs) == 1
    assert subs[0]["p256dh"] == "p2"

    database.delete_push_subscription("https://push.example.com/x")
    assert database.list_push_subscriptions() == []
