"""Hatırlatma (reminders) CRUD ve zamanlayıcı sorgusu testleri."""
from app import database


def test_create_and_get_reminder(tmp_db):
    rid = database.create_reminder({"text": "Faturayı öde", "remind_at": "2026-08-01 09:00"})
    r = database.get_reminder(rid)
    assert r["text"] == "Faturayı öde"
    assert r["remind_at"] == "2026-08-01 09:00"
    assert r["status"] == "bekliyor"
    assert r["notified_at"] is None


def test_create_reminder_with_relations(tmp_db):
    rid = database.create_reminder({
        "text": "Ayşe'ye dön", "remind_at": "2026-08-01 09:00",
        "related_email_id": 1, "related_event_id": 42,
    })
    r = database.get_reminder(rid)
    assert r["related_email_subject"] == "Proje toplantısı hakkında"
    assert r["related_event_title"] == "Haftalık Sprint"


def test_list_reminders_filters_by_status(tmp_db):
    a = database.create_reminder({"text": "A", "remind_at": "2026-08-01 09:00"})
    b = database.create_reminder({"text": "B", "remind_at": "2026-08-02 09:00"})
    database.complete_reminder(a, done=True)

    pending = database.list_reminders(status="bekliyor")
    done = database.list_reminders(status="tamamlandi")
    assert [r["id"] for r in pending] == [b]
    assert [r["id"] for r in done] == [a]


def test_list_reminders_upto_filters_by_time(tmp_db):
    early = database.create_reminder({"text": "Erken", "remind_at": "2026-08-01 09:00"})
    database.create_reminder({"text": "Geç", "remind_at": "2026-08-05 09:00"})

    rows = database.list_reminders(upto="2026-08-02 00:00")
    assert [r["id"] for r in rows] == [early]


def test_update_reminder_changes_fields(tmp_db):
    rid = database.create_reminder({"text": "Eski metin", "remind_at": "2026-08-01 09:00"})
    database.update_reminder(rid, text="Yeni metin", remind_at="2026-08-03 10:00")
    r = database.get_reminder(rid)
    assert r["text"] == "Yeni metin"
    assert r["remind_at"] == "2026-08-03 10:00"


def test_complete_reminder_toggle(tmp_db):
    rid = database.create_reminder({"text": "X", "remind_at": "2026-08-01 09:00"})
    database.complete_reminder(rid, done=True)
    assert database.get_reminder(rid)["status"] == "tamamlandi"
    database.complete_reminder(rid, done=False)
    assert database.get_reminder(rid)["status"] == "bekliyor"


def test_delete_reminder(tmp_db):
    rid = database.create_reminder({"text": "Silinecek", "remind_at": "2026-08-01 09:00"})
    database.delete_reminder(rid)
    assert database.get_reminder(rid) is None


def test_due_reminders_unnotified_only_returns_due_and_pending(tmp_db):
    due = database.create_reminder({"text": "Zamanı geldi", "remind_at": "2026-07-30 09:00"})
    future = database.create_reminder({"text": "Henüz değil", "remind_at": "2099-01-01 09:00"})
    already_done = database.create_reminder({"text": "Tamam", "remind_at": "2026-07-30 09:00"})
    database.complete_reminder(already_done, done=True)

    rows = database.due_reminders_unnotified("2026-07-31 00:00")
    ids = {r["id"] for r in rows}
    assert ids == {due}
    assert future not in ids


def test_due_reminders_unnotified_excludes_already_notified(tmp_db):
    rid = database.create_reminder({"text": "Zamanı geldi", "remind_at": "2026-07-30 09:00"})
    database.mark_reminder_notified(rid)

    rows = database.due_reminders_unnotified("2026-07-31 00:00")
    assert rows == []
