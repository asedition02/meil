"""Kalıcı Donna konuşmaları CRUD testleri (app/database.py)."""
from app import database


def test_create_conversation_defaults_title(tmp_db):
    cid = database.create_conversation()
    conv = database.get_conversation(cid)
    assert conv["title"] == "Yeni sohbet"


def test_create_conversation_with_title(tmp_db):
    cid = database.create_conversation("Fatura sorunu")
    conv = database.get_conversation(cid)
    assert conv["title"] == "Fatura sorunu"


def test_list_conversations_orders_by_most_recently_updated(tmp_db):
    a = database.create_conversation("A")
    b = database.create_conversation("B")
    database.add_donna_message(a, "user", "merhaba")  # a'yı günceller, en üste taşır

    rows = database.list_conversations()
    assert [r["id"] for r in rows] == [a, b]


def test_list_conversations_includes_last_message_preview(tmp_db):
    cid = database.create_conversation()
    database.add_donna_message(cid, "user", "İlk soru")
    database.add_donna_message(cid, "assistant", "İşte cevap")

    rows = database.list_conversations()
    assert rows[0]["last_message"] == "İşte cevap"


def test_rename_conversation(tmp_db):
    cid = database.create_conversation("Eski")
    database.rename_conversation(cid, "Yeni başlık")
    assert database.get_conversation(cid)["title"] == "Yeni başlık"


def test_rename_with_blank_title_falls_back_to_default(tmp_db):
    cid = database.create_conversation("Eski")
    database.rename_conversation(cid, "   ")
    assert database.get_conversation(cid)["title"] == "Yeni sohbet"


def test_delete_conversation_removes_messages_too(tmp_db):
    cid = database.create_conversation()
    database.add_donna_message(cid, "user", "soru")
    database.delete_conversation(cid)

    assert database.get_conversation(cid) is None
    assert database.get_conversation_messages(cid) == []


def test_add_and_get_messages_in_order(tmp_db):
    cid = database.create_conversation()
    database.add_donna_message(cid, "user", "Bugün ne var?")
    database.add_donna_message(cid, "assistant", "3 mail bekliyor.",
                               sources=[{"id": 1, "subject": "X", "sender": "Y"}])

    messages = database.get_conversation_messages(cid)
    assert [m["role"] for m in messages] == ["user", "assistant"]
    assert messages[0]["content"] == "Bugün ne var?"
    assert messages[1]["sources"] == [{"id": 1, "subject": "X", "sender": "Y"}]


def test_get_conversation_messages_respects_limit_and_keeps_chronological_order(tmp_db):
    cid = database.create_conversation()
    for i in range(5):
        database.add_donna_message(cid, "user", f"soru {i}")

    messages = database.get_conversation_messages(cid, limit=2)
    assert [m["content"] for m in messages] == ["soru 3", "soru 4"]


def test_messages_from_different_conversations_do_not_mix(tmp_db):
    a = database.create_conversation()
    b = database.create_conversation()
    database.add_donna_message(a, "user", "A sorusu")
    database.add_donna_message(b, "user", "B sorusu")

    assert [m["content"] for m in database.get_conversation_messages(a)] == ["A sorusu"]
    assert [m["content"] for m in database.get_conversation_messages(b)] == ["B sorusu"]
