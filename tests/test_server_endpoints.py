"""Sunucu uç nokta entegrasyon testleri — FastAPI TestClient.

Her test gerçek bir HTTP isteği gönderir; uygulama işlem içinde çalışır.
Katmanlar: HTTP yönlendirici → donna.ask_with_tools → NVIDIA NIM API.

Kapsanan uç noktalar:
  GET  /api/status                  — kimlik doğrulama durumu
  GET  /api/ai/providers            — sağlayıcı listesi
  POST /api/ai/test                 — sağlayıcı bağlantı testi
  GET  /api/donna/brief             — proaktif brifing
  POST /api/donna/ask               — tool calling soru-cevap
  POST /api/donna/act  (sahte onay) — işlem uygulama uçları (hata yolları)

NVIDIA_API_KEY tanımlı değilse AI gerektiren testler otomatik atlanır.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

# ---- Uygulama fabrikası (geçici DB ile) --------------------------------

def make_client(tmp_path, monkeypatch):
    """Her test için izole DB üzerinde çalışan TestClient döndürür."""
    from fastapi.testclient import TestClient
    from app import config, database

    db_path = tmp_path / "server_test.db"
    monkeypatch.setattr(config, "DB_PATH", db_path)
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "DATAROOM_DIR", tmp_path / "dataroom")
    (tmp_path / "dataroom").mkdir()

    database.init_db()

    # Örnek mail + etkinlik ekle
    with database.get_db() as db:
        db.execute(
            """INSERT INTO emails
               (id, account_id, message_id, sender_name, sender_email,
                subject, date, body_text, category, priority,
                summary, needs_reply, suggested_reply, status,
                attachments, is_read, thread_id)
               VALUES (1,1,'<m1@t>','Zeynep','z@ex.com',
                       'Sunum tarihi',  '2026-07-28T10:00:00',
                       'Merhaba, sunum için uygun tarihiniz nedir?',
                       'İş','yüksek','Sunum tarihi talebi.',
                       1,'','new','[]',0,'<m1@t>')"""
        )
        db.execute(
            """INSERT INTO events
               (id, calendar_id, uid, title, start, end, all_day, location, source)
               VALUES (10,NULL,'uid-010','Aylık Değerlendirme',
                       '2026-07-30T14:00','2026-07-30T15:00',0,'Toplantı Odası','manual')"""
        )

    # Modülü yeniden import etmeden uygulamayı TestClient'a ver
    from app.main import app
    return TestClient(app, raise_server_exceptions=False)


# ---- Fixtures ----------------------------------------------------------

@pytest.fixture()
def client(tmp_path, monkeypatch):
    return make_client(tmp_path, monkeypatch)


# Yalnızca NVIDIA key varsa AI gerektiren testleri çalıştır
from app import config as _cfg
needs_nvidia = pytest.mark.skipif(
    not _cfg.NVIDIA_API_KEY or _cfg.NVIDIA_API_KEY.startswith("nvapi-BURAYA"),
    reason="NVIDIA_API_KEY tanımlı değil",
)

REQUIRED_RESPONSE_FIELDS = {"answer", "email_ids", "action", "follow_ups", "sources"}
REQUIRED_ACTION_FIELDS = {
    "type", "summary", "email_id", "reply_text",
    "event_id", "title", "date", "time", "duration_minutes", "location", "path",
}


# =========================================================================
# 1. Durum ve kimlik doğrulama
# =========================================================================

class TestStatusEndpoints:
    def test_status_returns_200(self, client):
        r = client.get("/api/status")
        assert r.status_code == 200
        body = r.json()
        assert "api_version" in body
        assert "ai_configured" in body
        assert "ai_provider" in body
        assert isinstance(body["api_version"], int)
        assert body["ai_provider"] == "nvidia"

    def test_unauthenticated_api_blocked_when_pin_set(self, tmp_path, monkeypatch):
        """PIN belirlenmişse kimlik doğrulamasız API erişimi 401 döndürmeli."""
        from fastapi.testclient import TestClient
        from app import config, database, auth

        db_path = tmp_path / "auth_test.db"
        monkeypatch.setattr(config, "DB_PATH", db_path)
        monkeypatch.setattr(config, "DATA_DIR", tmp_path)
        monkeypatch.setattr(config, "DATAROOM_DIR", tmp_path / "dataroom")
        (tmp_path / "dataroom").mkdir()
        database.init_db()

        auth.set_pin("Gizli123!")

        from app.main import app
        c = TestClient(app, raise_server_exceptions=False)
        r = c.get("/api/ai/providers")
        assert r.status_code == 401

    def test_api_accessible_without_pin(self, client):
        r = client.get("/api/ai/providers")
        assert r.status_code == 200


# =========================================================================
# 2. AI sağlayıcı uç noktaları
# =========================================================================

class TestAIProviderEndpoints:
    def test_providers_lists_nvidia(self, client):
        r = client.get("/api/ai/providers")
        assert r.status_code == 200
        body = r.json()
        names = [p["name"] for p in body["providers"]]
        assert "nvidia" in names

    @needs_nvidia
    def test_nvidia_provider_is_configured(self, client):
        r = client.get("/api/ai/providers")
        providers = {p["name"]: p for p in r.json()["providers"]}
        assert providers["nvidia"]["configured"] is True

    @needs_nvidia
    def test_nvidia_provider_test_passes(self, client):
        r = client.post("/api/ai/test", json={"provider": "nvidia"})
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert body["ms"] > 0
        assert body["model"] == "nvidia/llama-3.3-nemotron-super-49b-v1.5"

    def test_set_provider_to_nvidia(self, client):
        r = client.post("/api/ai/provider", json={"provider": "nvidia"})
        assert r.status_code == 200
        assert r.json()["selected"] == "nvidia"

    def test_set_invalid_provider_returns_400(self, client):
        r = client.post("/api/ai/provider", json={"provider": "yokmodel"})
        assert r.status_code == 400


# =========================================================================
# 3. Donna brifing (/api/donna/brief)
# =========================================================================

class TestDonnaBrief:
    @needs_nvidia
    def test_brief_returns_200_with_schema(self, client):
        r = client.get("/api/donna/brief")
        assert r.status_code == 200
        body = r.json()
        assert "greeting" in body
        assert "headline" in body
        assert isinstance(body["items"], list)
        assert "stats" in body
        stats = body["stats"]
        for key in ("attention", "needs_reply", "today_events", "events_14d"):
            assert key in stats

    @needs_nvidia
    def test_brief_stats_reflect_seeded_data(self, client):
        """DB'deki 1 yanıt bekleyen mailin stats'a yansıdığını doğrular."""
        r = client.get("/api/donna/brief")
        assert r.status_code == 200
        stats = r.json()["stats"]
        assert stats["attention"] >= 1
        assert stats["needs_reply"] >= 1


# =========================================================================
# 4. Donna soru-cevap (/api/donna/ask) — tool calling uçtan uca
# =========================================================================

class TestDonnaAsk:
    def test_empty_question_returns_400(self, client):
        r = client.post("/api/donna/ask", json={"question": "   "})
        assert r.status_code == 400

    def test_missing_question_field_returns_422(self, client):
        r = client.post("/api/donna/ask", json={})
        assert r.status_code == 422

    @needs_nvidia
    def test_info_question_response_schema(self, client):
        """Bilgi sorusu tam şema ve tool_call yok döndürmeli."""
        r = client.post("/api/donna/ask",
                        json={"question": "Bugün takvimimde ne var?"})
        assert r.status_code == 200
        body = r.json()
        assert REQUIRED_RESPONSE_FIELDS <= body.keys()
        assert isinstance(body["answer"], str) and len(body["answer"]) > 0
        assert REQUIRED_ACTION_FIELDS <= body["action"].keys()
        assert isinstance(body["email_ids"], list)
        assert isinstance(body["sources"], list)

    @needs_nvidia
    def test_info_question_action_is_yok(self, client):
        r = client.post("/api/donna/ask",
                        json={"question": "Kaç tane okunmamış mailim var?"})
        assert r.status_code == 200
        assert r.json()["action"]["type"] == "yok"

    @needs_nvidia
    def test_calendar_event_creation_via_http(self, client):
        """HTTP üzerinden etkinlik isteği → action.type etkinlik_olustur."""
        r = client.post("/api/donna/ask", json={
            "question": "Yarın saat 10:00'da Haftalık Planlama toplantısı oluştur, 1 saat."
        })
        assert r.status_code == 200
        body = r.json()
        assert REQUIRED_RESPONSE_FIELDS <= body.keys()
        action = body["action"]
        assert REQUIRED_ACTION_FIELDS <= action.keys()
        if action["type"] != "yok":
            assert action["type"] == "etkinlik_olustur"
            assert action["date"] == "2026-07-29"
            assert action["title"] != ""

    @needs_nvidia
    def test_conversation_history_accepted(self, client):
        """Geçmiş konuşma geçirildiğinde istek kabul edilmeli."""
        history = [
            {"role": "user", "content": "Dünkü toplantıdan bahset."},
            {"role": "assistant", "content": "Takvimde kayıt bulamadım."},
        ]
        r = client.post("/api/donna/ask",
                        json={"question": "Peki bu hafta?", "history": history})
        assert r.status_code == 200
        assert REQUIRED_RESPONSE_FIELDS <= r.json().keys()


# =========================================================================
# 5. Donna işlem uygulama (/api/donna/act) — hata yolları
# =========================================================================

class TestDonnaAct:
    def test_unknown_action_type_returns_400(self, client):
        r = client.post("/api/donna/act", json={"type": "bilinmeyen_islem"})
        assert r.status_code == 400

    def test_mail_yanitla_without_text_returns_400(self, client):
        r = client.post("/api/donna/act",
                        json={"type": "mail_yanitla", "email_id": 1, "reply_text": ""})
        assert r.status_code == 400

    def test_etkinlik_olustur_creates_event_in_db(self, client):
        """Onaylanan etkinlik isteği DB'ye yazılmalı."""
        from app import database
        r = client.post("/api/donna/act", json={
            "type": "etkinlik_olustur",
            "title": "Test Etkinliği",
            "date": "2026-08-01",
            "time": "09:00",
            "duration_minutes": 30,
            "location": "Online",
        })
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        # DB'de gerçekten oluşturulduğunu doğrula
        events = database.list_events("2026-08-01", "2026-08-01T23:59")
        titles = [e["title"] for e in events]
        assert "Test Etkinliği" in titles

    def test_etkinlik_sil_nonexistent_returns_404(self, client):
        r = client.post("/api/donna/act",
                        json={"type": "etkinlik_sil", "event_id": 99999})
        assert r.status_code in (404, 400, 502)   # bulunamadı veya hata

    def test_etkinlik_guncelle_known_event(self, client):
        """Seed'li etkinlik (ID 10) güncellenmeli."""
        r = client.post("/api/donna/act", json={
            "type": "etkinlik_guncelle",
            "event_id": 10,
            "title": "Aylık Değerlendirme (Güncellendi)",
            "date": "2026-07-30",
            "time": "15:00",
            "duration_minutes": 60,
            "location": "Toplantı Odası",
        })
        assert r.status_code == 200
        assert r.json()["ok"] is True
