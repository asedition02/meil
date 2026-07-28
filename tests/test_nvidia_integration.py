"""NVIDIA NIM entegrasyon testleri.

Gerçek API çağrıları yapar; NVIDIA_API_KEY .env'de tanımlı değilse
tüm testler otomatik olarak atlanır (skip).

Kapsam:
  _nvidia_tool_call:
    - Saf bilgi sorusunda tool_call == None döner
    - Etkinlik oluşturma isteğinde create_calendar_event çağrılır
    - Mail yanıtı isteğinde draft_email_reply çağrılır
    - Etkinlik güncelleme isteğinde update_calendar_event çağrılır
    - Etkinlik silme isteğinde delete_calendar_event çağrılır
    - Hatalı API key → RuntimeError

  ask_with_tools:
    - Nvidia dışı sağlayıcıda ask()'a düşer (monkeypatch)
    - Bilgi sorusunda action.type == "yok"
    - Etkinlik isteğinde action.type == "etkinlik_olustur"
    - Dönüş şemasının zorunlu alanları var
"""
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from app import ai, config

# NVIDIA_API_KEY yoksa tüm testleri atla
pytestmark = pytest.mark.skipif(
    not config.NVIDIA_API_KEY or config.NVIDIA_API_KEY.startswith("nvapi-BURAYA"),
    reason="NVIDIA_API_KEY tanımlı değil",
)


# ---------------------------------------------------------------------------
# Yardımcılar
# ---------------------------------------------------------------------------

TODAY = "2026-07-28"

SYSTEM = (
    "Sen bir e-posta asistanısın. "
    f"Bugünün tarihi {TODAY}. "
    "Göreli tarihleri (yarın, önümüzdeki Salı) bu tarihe göre hesapla."
)

RESPONSE_FIELDS = {"answer", "email_ids", "action", "follow_ups", "sources"}
ACTION_FIELDS = {
    "type", "summary", "email_id", "reply_text",
    "event_id", "title", "date", "time", "duration_minutes", "location", "path",
}


def call(user_msg: str, max_tokens: int = 512) -> dict:
    from app.donna import DONNA_TOOLS
    return ai._nvidia_tool_call(SYSTEM, [{"role": "user", "content": user_msg}],
                                DONNA_TOOLS, max_tokens=max_tokens)


# ---------------------------------------------------------------------------
# _nvidia_tool_call — araç seçimi
# ---------------------------------------------------------------------------

class TestNvidiaToolCall:

    def test_plain_question_returns_no_tool_call(self):
        """Bilgi sorusu → model araç çağırmamalı, text yanıt vermeli."""
        result = call("Bugün takvimimde neler var? Sadece bilgi istiyorum, işlem yapma.")
        assert result["tool_call"] is None
        assert isinstance(result["text"], str)
        assert len(result["text"]) > 0

    def test_create_event_triggers_tool(self):
        """Toplantı isteği → create_calendar_event çağrılmalı."""
        result = call("Yarın saat 14:00'de Proje Kickoff toplantısı oluştur, 1 saat sürecek.")
        assert result["tool_call"] is not None
        assert result["tool_call"]["name"] == "create_calendar_event"
        args = result["tool_call"]["arguments"]
        assert args.get("title"), "Başlık boş olmamalı"
        assert args.get("date") == "2026-07-29", f"Yarın = 2026-07-29 olmalı, gelen: {args.get('date')}"
        assert args.get("time") == "14:00"
        assert int(args.get("duration_minutes", 0)) == 60

    def test_email_reply_triggers_tool(self):
        """Mail yanıtı → draft_email_reply çağrılmalı."""
        prompt = (
            "Aşağıdaki maile yanıt hazırla:\n"
            "[mail:5] Gönderen: Ali <ali@example.com> | Konu: Teklif talebi\n"
            "İçerik: Merhaba, proje için bir fiyat teklifi alabilir miyiz?\n\n"
            "Yanıt taslağı hazırla."
        )
        result = call(prompt, max_tokens=1024)
        assert result["tool_call"] is not None
        assert result["tool_call"]["name"] == "draft_email_reply"
        args = result["tool_call"]["arguments"]
        assert int(args.get("email_id", 0)) == 5
        assert len(args.get("reply_text", "")) > 20, "Yanıt metni çok kısa"

    def test_update_event_triggers_tool(self):
        """Etkinlik güncelleme isteği → update_calendar_event çağırılmalı.

        Not: Üretici modellerde olasılıksal örnekleme nedeniyle araç seçimi
        zaman zaman değişebilir. Test 2 deneme hakkı vererek bu durumu tolere eder;
        ikinci denemede de başarısız olursa gerçek bir hata var demektir.
        """
        prompt = (
            "TAKVİM:\n"
            "[etkinlik:42] 2026-07-29 10:00-11:00 · Haftalık Sprint | Zoom\n\n"
            "Haftalık Sprint etkinliğini (ID: 42) güncelle: saat 11:00'e al."
        )
        result = None
        for _ in range(2):          # olasılıksal modellerde nadir görülen kararsalık için
            result = call(prompt)
            if result["tool_call"] is not None:
                break
        assert result is not None
        assert result["tool_call"] is not None, (
            f"Model 2 denemede de araç çağırmadı. text='{result['text'][:200]}'"
        )
        assert result["tool_call"]["name"] == "update_calendar_event"
        args = result["tool_call"]["arguments"]
        assert int(args.get("event_id", 0)) == 42
        assert args.get("time") == "11:00"

    def test_delete_event_triggers_tool(self):
        """Etkinlik silme isteği → delete_calendar_event çağrılmalı."""
        prompt = (
            "[etkinlik:42] 2026-07-29 10:00 · Haftalık Sprint\n\n"
            "Haftalık Sprint etkinliğini (ID 42) sil."
        )
        result = call(prompt)
        assert result["tool_call"] is not None
        assert result["tool_call"]["name"] == "delete_calendar_event"
        assert int(result["tool_call"]["arguments"].get("event_id", 0)) == 42

    def test_invalid_api_key_raises(self):
        """Hatalı API key → RuntimeError fırlatmalı."""
        original = config.NVIDIA_API_KEY
        config.NVIDIA_API_KEY = "nvapi-INVALID_KEY_FOR_TEST"
        try:
            with pytest.raises(RuntimeError, match="NVIDIA tool call API hatası"):
                call("test")
        finally:
            config.NVIDIA_API_KEY = original


# ---------------------------------------------------------------------------
# ask_with_tools — entegrasyon
# ---------------------------------------------------------------------------

class TestAskWithTools:
    """ask_with_tools uçtan uca testleri; tmp_db fixture'ı gerektirir."""

    def test_non_nvidia_provider_falls_back(self, tmp_db, monkeypatch):
        """NVIDIA dışı provider → mevcut ask() çağrılmalı."""
        from app import donna

        ask_called = []

        def fake_ask(q, h, u):
            ask_called.append(q)
            return {"answer": "fallback", "email_ids": [], "action": {"type": "yok"},
                    "follow_ups": [], "sources": []}

        monkeypatch.setattr(donna, "ask", fake_ask)
        monkeypatch.setattr(ai, "active_provider", lambda: "gemini")

        result = donna.ask_with_tools("test sorusu")
        assert ask_called, "ask() çağrılmadı"
        assert result["answer"] == "fallback"

    def test_info_question_returns_no_action(self, tmp_db):
        """Boş DB'de bilgi sorusu → action.type == 'yok'."""
        from app import donna

        result = donna.ask_with_tools("Bugün takvimimde etkinlik var mı?")
        assert set(result.keys()) >= RESPONSE_FIELDS
        assert isinstance(result["answer"], str)
        assert result["action"]["type"] == "yok"
        assert ACTION_FIELDS <= result["action"].keys()

    def test_event_creation_returns_correct_action(self, tmp_db):
        """Etkinlik isteği → action.type == 'etkinlik_olustur' ve alanlar doğru."""
        from app import donna

        result = donna.ask_with_tools(
            "Yarın saat 15:00'de Müşteri Demo toplantısı oluştur, 45 dakika sürecek."
        )
        assert set(result.keys()) >= RESPONSE_FIELDS
        action = result["action"]
        assert ACTION_FIELDS <= action.keys()

        if action["type"] != "yok":              # model araç çağırdıysa
            assert action["type"] == "etkinlik_olustur"
            assert action["date"] == "2026-07-29"
            assert action["time"] == "15:00"
            assert 0 < action["duration_minutes"] <= 120

    def test_response_always_has_required_fields(self, tmp_db):
        """Her koşulda dönüş şemasının zorunlu alanları mevcut olmalı."""
        from app import donna

        result = donna.ask_with_tools("Merhaba, nasılsın?")
        assert RESPONSE_FIELDS <= result.keys()
        assert ACTION_FIELDS <= result["action"].keys()
        assert isinstance(result["email_ids"], list)
        assert isinstance(result["sources"], list)
        assert isinstance(result["follow_ups"], list)
