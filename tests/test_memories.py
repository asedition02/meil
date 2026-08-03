"""Donna hafızası (donna_memories) CRUD testleri."""
from app import database


def test_create_memory_defaults_source(tmp_db):
    mid = database.create_memory("Cuma günleri toplantı istemiyor")
    memories = database.list_memories()
    assert [m["id"] for m in memories] == [mid]
    assert memories[0]["content"] == "Cuma günleri toplantı istemiyor"
    assert memories[0]["source"] == "kullanici_komutu"


def test_create_memory_with_explicit_source(tmp_db):
    database.create_memory("Doğum günü 5 Mayıs", source="elle")
    assert database.list_memories()[0]["source"] == "elle"


def test_create_memory_trims_and_truncates(tmp_db):
    database.create_memory("  boşluklu  ")
    assert database.list_memories()[0]["content"] == "boşluklu"

    long_text = "a" * 600
    database.create_memory(long_text)
    truncated = [m for m in database.list_memories() if m["content"].startswith("aaa")][0]
    assert len(truncated["content"]) == 500


def test_list_memories_orders_newest_first(tmp_db):
    a = database.create_memory("İlk")
    b = database.create_memory("İkinci")

    rows = database.list_memories()
    assert [r["id"] for r in rows] == [b, a]


def test_delete_memory(tmp_db):
    mid = database.create_memory("Silinecek")
    database.delete_memory(mid)
    assert database.list_memories() == []
