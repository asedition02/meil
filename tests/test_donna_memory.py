"""Donna'nın kalıcı konuşma hafızası: database katmanı + bağlam entegrasyonu.

AI çağrısı gerektiren kısımlar (ask/ask_with_tools) ai._generate_json
sahtesiyle test edilir; gerçek ağ isteği yapılmaz.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# =========================================================================
# 1. database.py — donna_messages
# =========================================================================

class TestDonnaMessagesTable:
    def test_log_and_recent_roundtrip(self, tmp_db):
        from app import database

        database.log_donna_message("user", "Yarın toplantım var mı?")
        database.log_donna_message("assistant", "Yarın için kayıtlı bir etkinlik yok.")

        rows = database.recent_donna_messages(10)
        assert [r["role"] for r in rows] == ["user", "assistant"]
        assert rows[0]["content"] == "Yarın toplantım var mı?"
        assert rows[1]["content"] == "Yarın için kayıtlı bir etkinlik yok."

    def test_recent_is_chronological_oldest_first(self, tmp_db):
        from app import database

        for i in range(5):
            database.log_donna_message("user", f"mesaj {i}")

        rows = database.recent_donna_messages(3)
        assert [r["content"] for r in rows] == ["mesaj 2", "mesaj 3", "mesaj 4"]

    def test_empty_content_is_not_logged(self, tmp_db):
        from app import database

        database.log_donna_message("user", "   ")
        database.log_donna_message("user", "")
        assert database.recent_donna_messages(10) == []

    def test_search_matches_keyword_case_insensitive(self, tmp_db):
        from app import database

        database.log_donna_message("user", "Berbere ne zaman gitmiştim?")
        database.log_donna_message("assistant", "Geçen ay BERBER randevusu eklemiştin.")
        database.log_donna_message("user", "Faturaları kontrol et.")

        results = database.search_donna_messages("berber", 10)
        assert len(results) == 2
        assert all("berber" in r["content"].lower() for r in results)

    def test_search_without_tokens_returns_empty(self, tmp_db):
        from app import database

        database.log_donna_message("user", "merhaba")
        assert database.search_donna_messages("   ", 10) == []

    def test_search_respects_limit(self, tmp_db):
        from app import database

        for i in range(5):
            database.log_donna_message("user", f"berber randevusu {i}")

        assert len(database.search_donna_messages("berber", 2)) == 2


# =========================================================================
# 2. donna.gather_context / _context_text — hafıza entegrasyonu
# =========================================================================

class TestDonnaContextMemory:
    def test_gather_context_includes_recent_history(self, tmp_db):
        from app import database, donna

        database.log_donna_message("user", "Geçen hafta ne yapmıştım?")
        database.log_donna_message("assistant", "Sprint toplantısı vardı.")

        ctx = donna.gather_context()
        assert len(ctx["history_recent"]) == 2
        assert ctx["history_recent"][0]["role"] == "user"

    def test_gather_context_includes_related_history_for_question(self, tmp_db):
        from app import database, donna

        database.log_donna_message("user", "Berbere en son ne zaman gittim?")
        database.log_donna_message("assistant", "Kayıtlarda geçen ay bir berber etkinliği var.")
        database.log_donna_message("user", "Faturalarımı özetle.")

        ctx = donna.gather_context("berbere ne zaman gideceğim")
        related_texts = [h["content"] for h in ctx["history_related"]]
        assert any("berber" in t.lower() for t in related_texts)
        assert not any("fatura" in t.lower() for t in related_texts)

    def test_context_text_renders_memory_section(self, tmp_db):
        from app import database, donna

        database.log_donna_message("user", "Daha önce sordum: izin günüm ne zaman?")
        ctx = donna.gather_context()
        text = donna._context_text(ctx)
        assert "HAFIZA: SON KONUŞMALAR" in text
        assert "izin günüm ne zaman" in text

    def test_context_text_omits_memory_section_when_empty(self, tmp_db):
        from app import donna

        ctx = donna.gather_context()
        text = donna._context_text(ctx)
        assert "HAFIZA" not in text


# =========================================================================
# 3. donna.ask() — soru ve yanıtın hafızaya kaydedilmesi
# =========================================================================

class TestAskPersistsMemory:
    def test_ask_logs_question_and_answer(self, tmp_db, monkeypatch):
        from app import database, donna

        fake_result = {
            "answer": "Yarın için kayıtlı bir etkinliğin yok.",
            "email_ids": [],
            "action": {"type": "yok"},
            "follow_ups": [],
        }
        monkeypatch.setattr(donna.ai, "_generate_json", lambda *a, **k: dict(fake_result))

        donna.ask("Yarın toplantım var mı?")

        rows = database.recent_donna_messages(10)
        assert [r["role"] for r in rows] == ["user", "assistant"]
        assert rows[0]["content"] == "Yarın toplantım var mı?"
        assert rows[1]["content"] == fake_result["answer"]

    def test_next_ask_can_see_prior_turn_in_context(self, tmp_db, monkeypatch):
        from app import database, donna

        first = {"answer": "Geçen ay berber randevusu eklemiştin.",
                 "email_ids": [], "action": {"type": "yok"}, "follow_ups": []}
        monkeypatch.setattr(donna.ai, "_generate_json", lambda *a, **k: dict(first))
        donna.ask("Berbere en son ne zaman gittim?")

        ctx = donna.gather_context("berbere ne zaman gideceğim")
        related_texts = " ".join(h["content"] for h in ctx["history_related"])
        assert "berber" in related_texts.lower()
