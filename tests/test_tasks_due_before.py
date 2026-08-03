"""list_tasks(due_before=...) — Bugün ekranı için eklenen filtre."""
from app import database


def test_due_before_filters_out_later_and_dateless_tasks(tmp_db):
    overdue = database.create_task({"title": "Geçmiş", "due_date": "2026-07-01"})
    today = database.create_task({"title": "Bugün", "due_date": "2026-07-31"})
    database.create_task({"title": "Gelecek", "due_date": "2026-09-01"})
    database.create_task({"title": "Tarihsiz"})

    rows = database.list_tasks(due_before="2026-07-31")
    assert {r["id"] for r in rows} == {overdue, today}


def test_due_before_combines_with_status(tmp_db):
    done = database.create_task({"title": "Bitmiş", "due_date": "2026-07-01",
                                 "status": "tamamlandi"})
    open_task = database.create_task({"title": "Açık", "due_date": "2026-07-01"})

    rows = database.list_tasks(status="yapilacak", due_before="2026-07-31")
    ids = {r["id"] for r in rows}
    assert open_task in ids
    assert done not in ids
