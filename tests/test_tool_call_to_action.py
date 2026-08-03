"""_tool_call_to_action birim testleri.

Bu testler NVIDIA API çağrısı yapmaz; yalnızca donna._tool_call_to_action()
fonksiyonunun dönüşüm mantığını doğrular.

Kapsam:
- Dört araç tipi için geçerli dönüşüm (mail_yanitla, etkinlik_olustur/guncelle/sil)
- Bilinmeyen mail / etkinlik ID'si → action.type == "yok"
- Eksik zorunlu alanlar (email_id=0, reply_text="", title="", date="") → "yok"
- Bilinmeyen araç adı → "yok"
- Tüm dönüş sözlüklerinin ACTION_SCHEMA zorunlu alanlarını içerdiği
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.donna import _tool_call_to_action, _EMPTY_ACTION

# ACTION_SCHEMA'da required olarak belirtilen alanlar
REQUIRED_FIELDS = {
    "type", "summary", "email_id", "reply_text",
    "event_id", "title", "date", "time", "duration_minutes", "location", "path",
    "memory_text",
}


# ---------------------------------------------------------------------------
# Yardımcılar
# ---------------------------------------------------------------------------

def assert_schema_complete(action: dict):
    """Dönen dict'in tüm zorunlu alanları içerdiğini doğrular."""
    missing = REQUIRED_FIELDS - action.keys()
    assert not missing, f"Eksik alanlar: {missing}"


def empty_ctx():
    return {"attention": [], "related_mails": [], "events": []}


def ctx_with_email():
    return {
        "attention": [
            {
                "id": 1,
                "sender_name": "Ayşe Kaya",
                "sender_email": "ayse@example.com",
                "subject": "Proje toplantısı hakkında",
            }
        ],
        "related_mails": [],
        "events": [],
    }


def ctx_with_event():
    return {
        "attention": [],
        "related_mails": [],
        "events": [
            {
                "id": 42,
                "title": "Haftalık Sprint",
                "start": "2026-07-29T10:00",
                "end": "2026-07-29T11:00",
            }
        ],
    }


# ---------------------------------------------------------------------------
# draft_email_reply → mail_yanitla
# ---------------------------------------------------------------------------

class TestDraftEmailReply:
    def test_valid_reply_populates_action(self):
        action = _tool_call_to_action(
            "draft_email_reply",
            {"email_id": 1, "reply_text": "Merhaba, evet uygun.\n\nİyi çalışmalar,\nAhmet"},
            ctx_with_email(),
        )
        assert action["type"] == "mail_yanitla"
        assert action["email_id"] == 1
        assert "evet uygun" in action["reply_text"]
        assert action["mail_to"] == "Ayşe Kaya"
        assert action["mail_subject"] == "Proje toplantısı hakkında"
        assert "Ayşe Kaya" in action["summary"]
        assert_schema_complete(action)

    def test_unknown_email_id_returns_yok(self):
        action = _tool_call_to_action(
            "draft_email_reply",
            {"email_id": 999, "reply_text": "Yanıt"},
            ctx_with_email(),
        )
        assert action["type"] == "yok"
        assert_schema_complete(action)

    def test_zero_email_id_returns_yok(self):
        action = _tool_call_to_action(
            "draft_email_reply",
            {"email_id": 0, "reply_text": "Yanıt"},
            ctx_with_email(),
        )
        assert action["type"] == "yok"

    def test_empty_reply_text_returns_yok(self):
        action = _tool_call_to_action(
            "draft_email_reply",
            {"email_id": 1, "reply_text": ""},
            ctx_with_email(),
        )
        assert action["type"] == "yok"

    def test_missing_reply_text_key_returns_yok(self):
        action = _tool_call_to_action(
            "draft_email_reply",
            {"email_id": 1},
            ctx_with_email(),
        )
        assert action["type"] == "yok"

    def test_related_mail_also_searchable(self):
        """related_mails listesindeki mail de bulunabilmeli."""
        ctx = {
            "attention": [],
            "related_mails": [
                {
                    "id": 7,
                    "sender_name": "Mehmet",
                    "sender_email": "mehmet@example.com",
                    "subject": "Rapor",
                }
            ],
            "events": [],
        }
        action = _tool_call_to_action(
            "draft_email_reply",
            {"email_id": 7, "reply_text": "Tamam, ilettim."},
            ctx,
        )
        assert action["type"] == "mail_yanitla"
        assert action["email_id"] == 7
        assert action["mail_to"] == "Mehmet"


# ---------------------------------------------------------------------------
# create_calendar_event → etkinlik_olustur
# ---------------------------------------------------------------------------

class TestCreateCalendarEvent:
    def test_valid_event_populates_action(self):
        action = _tool_call_to_action(
            "create_calendar_event",
            {"title": "Müşteri Görüşmesi", "date": "2026-07-30",
             "time": "14:00", "duration_minutes": 90, "location": "Ofis"},
            empty_ctx(),
        )
        assert action["type"] == "etkinlik_olustur"
        assert action["title"] == "Müşteri Görüşmesi"
        assert action["date"] == "2026-07-30"
        assert action["time"] == "14:00"
        assert action["duration_minutes"] == 90
        assert action["location"] == "Ofis"
        assert "Müşteri Görüşmesi" in action["summary"]
        assert "2026-07-30" in action["summary"]
        assert_schema_complete(action)

    def test_all_day_event_empty_time(self):
        action = _tool_call_to_action(
            "create_calendar_event",
            {"title": "İzin Günü", "date": "2026-08-01",
             "time": "", "duration_minutes": 60},
            empty_ctx(),
        )
        assert action["type"] == "etkinlik_olustur"
        assert action["time"] == ""

    def test_default_duration_when_missing(self):
        action = _tool_call_to_action(
            "create_calendar_event",
            {"title": "Toplantı", "date": "2026-07-30"},
            empty_ctx(),
        )
        assert action["type"] == "etkinlik_olustur"
        assert action["duration_minutes"] == 60   # varsayılan

    def test_missing_title_returns_yok(self):
        action = _tool_call_to_action(
            "create_calendar_event",
            {"title": "", "date": "2026-07-30", "duration_minutes": 60},
            empty_ctx(),
        )
        assert action["type"] == "yok"

    def test_missing_date_returns_yok(self):
        action = _tool_call_to_action(
            "create_calendar_event",
            {"title": "Toplantı", "date": "", "duration_minutes": 60},
            empty_ctx(),
        )
        assert action["type"] == "yok"


# ---------------------------------------------------------------------------
# update_calendar_event → etkinlik_guncelle
# ---------------------------------------------------------------------------

class TestUpdateCalendarEvent:
    def test_known_event_includes_meta(self):
        action = _tool_call_to_action(
            "update_calendar_event",
            {"event_id": 42, "title": "Haftalık Sprint v2",
             "date": "2026-07-29", "time": "11:00", "duration_minutes": 60},
            ctx_with_event(),
        )
        assert action["type"] == "etkinlik_guncelle"
        assert action["event_id"] == 42
        assert action["title"] == "Haftalık Sprint v2"
        assert action["event_title"] == "Haftalık Sprint"      # ctx'ten
        assert action["event_when"] == "2026-07-29 10:00"      # ctx'ten
        assert "Sprint" in action["summary"]
        assert_schema_complete(action)

    def test_unknown_event_still_creates_action(self):
        """Bilinmeyen event_id olsa bile etkinlik_guncelle üretilmeli (ID geçerliyse)."""
        action = _tool_call_to_action(
            "update_calendar_event",
            {"event_id": 99, "title": "Yeni Toplantı",
             "date": "2026-07-31", "duration_minutes": 30},
            empty_ctx(),
        )
        assert action["type"] == "etkinlik_guncelle"
        assert action["event_id"] == 99
        assert "event_title" not in action          # ctx'te yok

    def test_zero_event_id_returns_yok(self):
        action = _tool_call_to_action(
            "update_calendar_event",
            {"event_id": 0, "title": "X", "date": "2026-07-30", "duration_minutes": 60},
            empty_ctx(),
        )
        assert action["type"] == "yok"


# ---------------------------------------------------------------------------
# delete_calendar_event → etkinlik_sil
# ---------------------------------------------------------------------------

class TestDeleteCalendarEvent:
    def test_known_event_includes_title(self):
        action = _tool_call_to_action(
            "delete_calendar_event",
            {"event_id": 42},
            ctx_with_event(),
        )
        assert action["type"] == "etkinlik_sil"
        assert action["event_id"] == 42
        assert action["event_title"] == "Haftalık Sprint"
        assert "Sprint" in action["summary"]
        assert_schema_complete(action)

    def test_unknown_event_still_deletes(self):
        action = _tool_call_to_action(
            "delete_calendar_event",
            {"event_id": 77},
            empty_ctx(),
        )
        assert action["type"] == "etkinlik_sil"
        assert action["event_id"] == 77
        assert "77" in action["summary"]

    def test_zero_event_id_returns_yok(self):
        action = _tool_call_to_action(
            "delete_calendar_event",
            {"event_id": 0},
            empty_ctx(),
        )
        assert action["type"] == "yok"


# ---------------------------------------------------------------------------
# remember_fact → hafiza_ekle
# ---------------------------------------------------------------------------

class TestRememberFact:
    def test_valid_content_populates_action(self):
        action = _tool_call_to_action(
            "remember_fact",
            {"content": "Cuma günleri toplantı istemiyor"},
            empty_ctx(),
        )
        assert action["type"] == "hafiza_ekle"
        assert action["memory_text"] == "Cuma günleri toplantı istemiyor"
        assert "Cuma günleri toplantı istemiyor" in action["summary"]
        assert_schema_complete(action)

    def test_empty_content_returns_yok(self):
        action = _tool_call_to_action("remember_fact", {"content": ""}, empty_ctx())
        assert action["type"] == "yok"

    def test_missing_content_key_returns_yok(self):
        action = _tool_call_to_action("remember_fact", {}, empty_ctx())
        assert action["type"] == "yok"

    def test_whitespace_only_content_returns_yok(self):
        action = _tool_call_to_action("remember_fact", {"content": "   "}, empty_ctx())
        assert action["type"] == "yok"


# ---------------------------------------------------------------------------
# Bilinmeyen araç adı
# ---------------------------------------------------------------------------

class TestUnknownTool:
    def test_unknown_name_returns_yok(self):
        action = _tool_call_to_action("unknown_tool", {}, empty_ctx())
        assert action["type"] == "yok"
        assert_schema_complete(action)

    def test_empty_name_returns_yok(self):
        action = _tool_call_to_action("", {}, empty_ctx())
        assert action["type"] == "yok"


# ---------------------------------------------------------------------------
# _EMPTY_ACTION şema bütünlüğü
# ---------------------------------------------------------------------------

def test_empty_action_has_all_required_fields():
    """_EMPTY_ACTION sabitinin ACTION_SCHEMA'yı karşıladığını doğrular."""
    assert_schema_complete(_EMPTY_ACTION)
    assert _EMPTY_ACTION["type"] == "yok"
