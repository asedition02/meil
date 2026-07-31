"""Cevap bekliyorum (awaiting_replies) CRUD ve otomatik çözümleme testleri."""
from app import database


def _create(tmp_db, **overrides):
    data = {
        "account_id": 1, "to_email": "ayse@example.com", "to_name": "Ayşe",
        "subject": "Teklif", "message_id": "<sent-1@meil>",
        "due_at": "2026-08-01 09:00",
    }
    data.update(overrides)
    return database.create_awaiting_reply(data)


def test_create_and_get(tmp_db):
    aid = _create(tmp_db)
    row = database.get_awaiting_reply(aid)
    assert row["to_email"] == "ayse@example.com"
    assert row["status"] == "bekliyor"
    assert row["resolved_at"] is None


def test_list_awaiting_replies_filters_by_status(tmp_db):
    a = _create(tmp_db, message_id="<a@meil>")
    b = _create(tmp_db, message_id="<b@meil>")
    database.resolve_awaiting_reply(a)

    pending = database.list_awaiting_replies(status="bekliyor")
    resolved = database.list_awaiting_replies(status="cevaplandi")
    assert [r["id"] for r in pending] == [b]
    assert [r["id"] for r in resolved] == [a]


def test_manual_resolve(tmp_db):
    aid = _create(tmp_db)
    database.resolve_awaiting_reply(aid)
    row = database.get_awaiting_reply(aid)
    assert row["status"] == "cevaplandi"
    assert row["resolved_at"] is not None


def test_cancel_deletes_row(tmp_db):
    aid = _create(tmp_db)
    database.cancel_awaiting_reply(aid)
    assert database.get_awaiting_reply(aid) is None


def test_auto_resolve_matches_in_reply_to(tmp_db):
    aid = _create(tmp_db, message_id="<sent-42@meil>")
    with database.get_db() as db:
        db.execute(
            """INSERT INTO emails (account_id, message_id, sender_name, sender_email,
                   subject, date, body_text, in_reply_to, refs, thread_id)
               VALUES (1, '<incoming-1@them>', 'Ayşe', 'ayse@example.com',
                       'Re: Teklif', '2026-07-31T10:00:00', 'Tamamdır',
                       '<sent-42@meil>', '<sent-42@meil>', '<sent-42@meil>')"""
        )

    resolved = database.resolve_awaiting_replies_by_headers()

    assert resolved == 1
    row = database.get_awaiting_reply(aid)
    assert row["status"] == "cevaplandi"
    assert row["resolved_email_id"] is not None


def test_auto_resolve_matches_references_chain(tmp_db):
    aid = _create(tmp_db, message_id="<sent-7@meil>")
    with database.get_db() as db:
        db.execute(
            """INSERT INTO emails (account_id, message_id, sender_name, sender_email,
                   subject, date, body_text, in_reply_to, refs, thread_id)
               VALUES (1, '<incoming-2@them>', 'Ayşe', 'ayse@example.com',
                       'Re: Teklif', '2026-07-31T10:00:00', 'Tamamdır',
                       '<other@them>', '<root@x> <sent-7@meil>', '<root@x>')"""
        )

    resolved = database.resolve_awaiting_replies_by_headers()
    assert resolved == 1


def test_auto_resolve_does_not_touch_unrelated_replies(tmp_db):
    aid = _create(tmp_db, message_id="<sent-99@meil>")
    with database.get_db() as db:
        db.execute(
            """INSERT INTO emails (account_id, message_id, sender_name, sender_email,
                   subject, date, body_text, in_reply_to, refs, thread_id)
               VALUES (1, '<incoming-3@them>', 'Biri', 'biri@example.com',
                       'Alakasız', '2026-07-31T10:00:00', 'Selam',
                       '<something-else@x>', '', '<something-else@x>')"""
        )

    resolved = database.resolve_awaiting_replies_by_headers()
    assert resolved == 0
    assert database.get_awaiting_reply(aid)["status"] == "bekliyor"


def test_due_awaiting_replies_unnotified(tmp_db):
    due = _create(tmp_db, message_id="<due@meil>", due_at="2000-01-01 00:00")
    future = _create(tmp_db, message_id="<future@meil>", due_at="2099-01-01 00:00")

    rows = database.due_awaiting_replies_unnotified("2026-07-31 00:00")
    ids = {r["id"] for r in rows}
    assert ids == {due}
    assert future not in ids


def test_due_awaiting_replies_excludes_notified(tmp_db):
    aid = _create(tmp_db, due_at="2000-01-01 00:00")
    database.mark_awaiting_reply_notified(aid)
    rows = database.due_awaiting_replies_unnotified("2026-07-31 00:00")
    assert rows == []
