"""Cevap bekliyorum bildirim işi testleri (app/awaiting_reply_notify.py)."""
from unittest.mock import patch

from app import awaiting_reply_notify, database


def _make_account(tmp_db):
    return database.create_account({
        "email": "ben@example.com", "password": "gizli",
        "imap_host": "imap.example.com", "smtp_host": "smtp.example.com",
    })


def _create_awaiting(**overrides):
    data = {
        "account_id": 1, "to_email": "ayse@example.com", "to_name": "Ayşe",
        "subject": "Teklif", "message_id": "<sent-1@meil>",
        "due_at": "2000-01-01 00:00",
    }
    data.update(overrides)
    return database.create_awaiting_reply(data)


def test_resolves_via_header_match_before_notifying(tmp_db):
    _make_account(tmp_db)
    aid = _create_awaiting(message_id="<sent-42@meil>", due_at="2000-01-01 00:00")
    with database.get_db() as db:
        db.execute(
            """INSERT INTO emails (account_id, message_id, sender_name, sender_email,
                   subject, date, body_text, in_reply_to, refs, thread_id)
               VALUES (1, '<incoming-1@them>', 'Ayşe', 'ayse@example.com',
                       'Re: Teklif', '2026-07-31T10:00:00', 'Tamam',
                       '<sent-42@meil>', '<sent-42@meil>', '<sent-42@meil>')"""
        )

    with patch("app.email_client.send_message") as send:
        awaiting_reply_notify.resolve_and_notify()

    send.assert_not_called()  # zaten çözüldü, bildirime gerek yok
    assert database.get_awaiting_reply(aid)["status"] == "cevaplandi"


def test_notifies_unresolved_due_record(tmp_db):
    _make_account(tmp_db)
    aid = _create_awaiting()

    with patch("app.email_client.send_message") as send:
        awaiting_reply_notify.resolve_and_notify()

    send.assert_called_once()
    assert database.get_awaiting_reply(aid)["notified_at"] is not None


def test_no_account_skips_silently(tmp_db):
    _create_awaiting()
    with patch("app.email_client.send_message") as send:
        awaiting_reply_notify.resolve_and_notify()  # patlamamalı
    send.assert_not_called()


def test_not_due_yet_is_not_notified(tmp_db):
    _make_account(tmp_db)
    _create_awaiting(due_at="2099-01-01 00:00")
    with patch("app.email_client.send_message") as send:
        awaiting_reply_notify.resolve_and_notify()
    send.assert_not_called()


def test_send_failure_does_not_mark_notified(tmp_db):
    _make_account(tmp_db)
    aid = _create_awaiting()
    with patch("app.email_client.send_message", side_effect=RuntimeError("smtp down")):
        awaiting_reply_notify.resolve_and_notify()  # patlamamalı
    assert database.get_awaiting_reply(aid)["notified_at"] is None
