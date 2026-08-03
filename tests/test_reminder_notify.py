"""Hatırlatma e-posta bildirimi testleri (app/reminder_notify.py)."""
from unittest.mock import patch

from app import database, reminder_notify


def _make_account(tmp_db):
    return database.create_account({
        "email": "ben@example.com", "password": "gizli",
        "imap_host": "imap.example.com", "smtp_host": "smtp.example.com",
    })


def test_no_due_reminders_sends_nothing(tmp_db):
    _make_account(tmp_db)
    with patch("app.email_client.send_message") as send:
        reminder_notify.notify_due_reminders()
    send.assert_not_called()


def test_no_account_configured_skips_silently(tmp_db):
    database.create_reminder({"text": "X", "remind_at": "2000-01-01 00:00"})
    with patch("app.email_client.send_message") as send:
        reminder_notify.notify_due_reminders()  # patlamamalı
    send.assert_not_called()


def test_due_reminder_sends_and_marks_notified(tmp_db):
    _make_account(tmp_db)
    rid = database.create_reminder({"text": "Faturayı öde", "remind_at": "2000-01-01 00:00"})

    with patch("app.email_client.send_message") as send:
        reminder_notify.notify_due_reminders()

    send.assert_called_once()
    args = send.call_args[0]
    assert args[1] == "ben@example.com"          # kendi hesabına gönderilir
    assert "Faturayı öde" in args[2]              # konu satırında
    assert database.get_reminder(rid)["notified_at"] is not None


def test_already_notified_reminder_is_not_resent(tmp_db):
    _make_account(tmp_db)
    rid = database.create_reminder({"text": "X", "remind_at": "2000-01-01 00:00"})
    database.mark_reminder_notified(rid)

    with patch("app.email_client.send_message") as send:
        reminder_notify.notify_due_reminders()

    send.assert_not_called()


def test_future_reminder_is_not_notified(tmp_db):
    _make_account(tmp_db)
    database.create_reminder({"text": "Henüz değil", "remind_at": "2099-01-01 00:00"})

    with patch("app.email_client.send_message") as send:
        reminder_notify.notify_due_reminders()

    send.assert_not_called()


def test_send_failure_does_not_mark_notified_and_does_not_raise(tmp_db):
    _make_account(tmp_db)
    rid = database.create_reminder({"text": "X", "remind_at": "2000-01-01 00:00"})

    with patch("app.email_client.send_message", side_effect=RuntimeError("smtp down")):
        reminder_notify.notify_due_reminders()  # patlamamalı

    assert database.get_reminder(rid)["notified_at"] is None
