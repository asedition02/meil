"""Ortak pytest fixture'ları.

* tmp_db  — her test için izole, geçici bir SQLite veritabanı kurar.
            config.DB_PATH'i geçici dosyaya yönlendirir; test bitince temizler.
* sample_ctx — donna.gather_context() çıktısının yerini tutan hazır bağlam sözlüğü.
               Gerçek DB sorgusu olmadan _tool_call_to_action / ask_with_tools testlerinde kullanılır.
"""
import os
import tempfile
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Geçici veritabanı
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_db(monkeypatch, tmp_path):
    """Her test için sıfırdan oluşturulan, izole SQLite DB'si.

    config.DB_PATH geçici dizine yönlendirilir; test tamamlandığında
    pytest otomatik olarak temizler.
    """
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))

    from app import config, database

    db_path = tmp_path / "test_meil.db"
    monkeypatch.setattr(config, "DB_PATH", db_path)

    # Veri dizinleri de geçici olsun
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "DATAROOM_DIR", tmp_path / "dataroom")
    (tmp_path / "dataroom").mkdir()

    database.init_db()

    # --- Örnek mail ---
    with database.get_db() as db:
        db.execute(
            """INSERT INTO emails
               (id, account_id, message_id, sender_name, sender_email,
                subject, date, body_text, category, priority,
                summary, needs_reply, suggested_reply, status,
                attachments, is_read, thread_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                1, 1, "<msg-001@test>",
                "Ayşe Kaya", "ayse@example.com",
                "Proje toplantısı hakkında",
                "2026-07-28T09:00:00",
                "Merhaba, yarın saat 10:00'da toplantı yapalım mı?",
                "İş", "yüksek",
                "Proje toplantısı talebini içeren mail.",
                1, "", "new",
                "[]", 0, "<msg-001@test>",
            ),
        )
        # --- Örnek takvim etkinliği ---
        db.execute(
            """INSERT INTO events
               (id, calendar_id, uid, title, start, end, all_day, location, source)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                42, None, "uid-042",
                "Haftalık Sprint", "2026-07-29T10:00", "2026-07-29T11:00",
                0, "Zoom", "manual",
            ),
        )

    yield db_path


# ---------------------------------------------------------------------------
# Hazır bağlam sözlüğü (DB gerektirmeden)
# ---------------------------------------------------------------------------

@pytest.fixture()
def sample_ctx():
    """donna.gather_context() çıktısıyla aynı yapıda örnek bağlam.

    İlgili mail ve etkinlik bilgilerini içerir; _tool_call_to_action
    ve ask_with_tools birim testlerinde kullanılır.
    """
    return {
        "today": "2026-07-28",
        "now": "2026-07-28 14:00",
        "weekday": "Salı",
        "counts": {"total": 1, "unread": 1, "needs_reply": 1},
        "attention": [
            {
                "id": 1,
                "sender_name": "Ayşe Kaya",
                "sender_email": "ayse@example.com",
                "subject": "Proje toplantısı hakkında",
                "date": "2026-07-28T09:00:00",
                "body_text": "Merhaba, yarın saat 10:00'da toplantı yapalım mı?",
                "category": "İş",
                "priority": "yüksek",
                "summary": "Proje toplantısı talebi.",
                "needs_reply": True,
                "is_read": False,
                "starred": False,
                "status": "new",
                "event_json": None,
            }
        ],
        "events": [
            {
                "id": 42,
                "uid": "uid-042",
                "title": "Haftalık Sprint",
                "start": "2026-07-29T10:00",
                "end": "2026-07-29T11:00",
                "all_day": False,
                "location": "Zoom",
                "calendar_name": "Meil",
            }
        ],
        "invoices": [],
        "docs": [],
        "related_mails": [],
        "related_docs": [],
    }
