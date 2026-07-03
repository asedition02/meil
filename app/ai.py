"""Claude ile mail tasnifi, özet ve yanıt önerisi."""
import json

import anthropic

from . import config

CATEGORIES = [
    "Önemli",
    "İş",
    "Kişisel",
    "Fatura/Finans",
    "Bülten",
    "Tanıtım/Reklam",
    "Spam",
    "Diğer",
]

PRIORITIES = ["yüksek", "orta", "düşük"]

TRIAGE_SCHEMA = {
    "type": "object",
    "properties": {
        "category": {"type": "string", "enum": CATEGORIES},
        "priority": {"type": "string", "enum": PRIORITIES},
        "summary": {
            "type": "string",
            "description": "Mailin 1-3 cümlelik Türkçe özeti.",
        },
        "needs_reply": {
            "type": "boolean",
            "description": "Bu maile yanıt vermek gerekiyor mu?",
        },
        "suggested_reply": {
            "type": "string",
            "description": (
                "Yanıt gerekiyorsa gönderilmeye hazır, mailin dilinde yazılmış "
                "kibar bir yanıt taslağı. Yanıt gerekmiyorsa boş string."
            ),
        },
    },
    "required": ["category", "priority", "summary", "needs_reply", "suggested_reply"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """Sen bir e-posta asistanısın. Kullanıcının gelen kutusundaki \
mailleri tasnif ediyor, özetliyor ve gerektiğinde yanıt taslağı hazırlıyorsun.

Kurallar:
- Özeti her zaman Türkçe yaz.
- Yanıt taslağını gelen mailin dilinde yaz (Türkçe mail → Türkçe yanıt, \
İngilizce mail → İngilizce yanıt).
- Yanıt taslağı doğrudan gönderilebilecek olgunlukta olsun: selamlama ile başla, \
kibar bir kapanışla bitir. Uydurma bilgi ekleme; emin olamadığın yerlerde \
[KÖŞELİ PARANTEZ] içinde doldurulacak alan bırak.
- Toplu bülten, reklam ve spam maillerine yanıt önerme (needs_reply: false).
- Fatura, ödeme, resmi kurum, son tarih içeren mailleri yüksek öncelikli değerlendir."""

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        if not config.ANTHROPIC_API_KEY:
            raise RuntimeError("ANTHROPIC_API_KEY ayarlanmalı.")
        _client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    return _client


def _email_prompt(sender: str, subject: str, date: str, body: str, attachments: list[str]) -> str:
    body = (body or "")[:15000]
    att = ", ".join(attachments) if attachments else "yok"
    return (
        f"Gönderen: {sender}\n"
        f"Konu: {subject}\n"
        f"Tarih: {date}\n"
        f"Ekler: {att}\n\n"
        f"--- MAİL İÇERİĞİ ---\n{body}"
    )


def triage_email(sender: str, subject: str, date: str, body: str,
                 attachments: list[str], user_name: str = "") -> dict:
    """Maili sınıflandırır, özetler ve yanıt taslağı üretir."""
    client = _get_client()
    system = SYSTEM_PROMPT
    if user_name:
        system += f"\n- Kullanıcının adı: {user_name}. Yanıtları bu isimle imzala."
    response = client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=2048,
        system=system,
        output_config={"format": {"type": "json_schema", "schema": TRIAGE_SCHEMA}},
        messages=[
            {
                "role": "user",
                "content": "Aşağıdaki maili tasnif et:\n\n"
                + _email_prompt(sender, subject, date, body, attachments),
            }
        ],
    )
    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text)


def regenerate_reply(sender: str, subject: str, date: str, body: str,
                     instruction: str = "", user_name: str = "") -> str:
    """Kullanıcının ek talimatıyla yeni bir yanıt taslağı üretir."""
    client = _get_client()
    system = SYSTEM_PROMPT
    if user_name:
        system += f"\n- Kullanıcının adı: {user_name}. Yanıtları bu isimle imzala."
    prompt = (
        "Aşağıdaki maile gönderilmeye hazır bir yanıt taslağı yaz. "
        "Sadece yanıt metnini yaz, başka açıklama ekleme.\n"
    )
    if instruction:
        prompt += f"\nKullanıcının talimatı: {instruction}\n"
    prompt += "\n" + _email_prompt(sender, subject, date, body, [])
    response = client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=2048,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    return next(b.text for b in response.content if b.type == "text").strip()
