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
        "detected_event": {
            "type": "object",
            "description": "Mailde geçen toplantı, randevu, etkinlik veya son tarih.",
            "properties": {
                "exists": {
                    "type": "boolean",
                    "description": "Mailde takvime eklenebilecek somut bir etkinlik/toplantı/son tarih var mı?",
                },
                "title": {"type": "string", "description": "Etkinliğin kısa Türkçe başlığı."},
                "date": {
                    "type": "string",
                    "description": "YYYY-MM-DD. 'Yarın', 'önümüzdeki salı' gibi göreli ifadeleri mailin tarihine göre hesapla. Tarih belirsizse boş string.",
                },
                "time": {
                    "type": "string",
                    "description": "HH:MM (24 saat). Saat belirtilmemişse boş string.",
                },
                "duration_minutes": {
                    "type": "integer",
                    "description": "Tahmini süre dakika cinsinden; bilinmiyorsa 60.",
                },
                "location": {
                    "type": "string",
                    "description": "Yer veya çevrimiçi bağlantı; yoksa boş string.",
                },
            },
            "required": ["exists", "title", "date", "time", "duration_minutes", "location"],
            "additionalProperties": False,
        },
    },
    "required": ["category", "priority", "summary", "needs_reply", "suggested_reply", "detected_event"],
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
- Fatura, ödeme, resmi kurum, son tarih içeren mailleri yüksek öncelikli değerlendir.
- Mailde somut bir toplantı, randevu, etkinlik veya son ödeme/teslim tarihi geçiyorsa \
detected_event.exists=true yap ve alanlarını doldur. Tarihi kesin olmayan, geçmişte \
kalan veya belirsiz ("bir ara görüşelim" gibi) ifadeler için exists=false bırak."""

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


COMPOSE_SCHEMA = {
    "type": "object",
    "properties": {
        "subject": {"type": "string", "description": "Mailin kısa, net konusu."},
        "body": {
            "type": "string",
            "description": "Gönderilmeye hazır mail metni: selamlama ile başlar, kibar kapanışla biter.",
        },
    },
    "required": ["subject", "body"],
    "additionalProperties": False,
}


def compose_email(instruction: str, to: str = "", subject: str = "",
                  user_name: str = "") -> dict:
    """Kullanıcının talimatından yeni bir mail taslağı üretir."""
    client = _get_client()
    system = (
        "Sen bir e-posta asistanısın. Kullanıcının talimatına göre gönderilmeye hazır "
        "bir mail yazıyorsun.\n"
        "- Talimat hangi dildeyse maili o dilde yaz (varsayılan Türkçe).\n"
        "- Selamlama ile başla, kibar bir kapanışla bitir.\n"
        "- Uydurma bilgi ekleme; emin olamadığın yerlerde [KÖŞELİ PARANTEZ] içinde "
        "doldurulacak alan bırak."
    )
    if user_name:
        system += f"\n- Kullanıcının adı: {user_name}. Maili bu isimle imzala."
    prompt = f"Talimat: {instruction}\n"
    if to:
        prompt += f"Alıcı: {to}\n"
    if subject:
        prompt += f"Konu (kullanıcı belirledi, aynen koru): {subject}\n"
    response = client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=2048,
        system=system,
        output_config={"format": {"type": "json_schema", "schema": COMPOSE_SCHEMA}},
        messages=[{"role": "user", "content": prompt}],
    )
    text = next(b.text for b in response.content if b.type == "text")
    result = json.loads(text)
    if subject:
        result["subject"] = subject
    return result


DOC_TYPES = ["Fatura", "Sözleşme", "Dekont/Makbuz", "Teklif", "Rapor",
             "Sunum", "CV/Özgeçmiş", "Resmi Yazı", "Diğer"]

DOC_SCHEMA = {
    "type": "object",
    "properties": {
        "doc_type": {"type": "string", "enum": DOC_TYPES},
        "summary": {
            "type": "string",
            "description": "Belgenin 1-2 cümlelik Türkçe özeti: ne belgesi, kimden/kime, ne hakkında.",
        },
        "tags": {
            "type": "array",
            "items": {"type": "string"},
            "description": "2-5 kısa, küçük harfli Türkçe etiket (ör. kira, sözleşme, 2026).",
        },
        "doc_date": {
            "type": "string",
            "description": "Belgenin kendi tarihi (fatura/sözleşme tarihi) YYYY-MM-DD. Yoksa boş string.",
        },
        "invoice": {
            "type": "object",
            "description": "Belge bir fatura/dekont/ödeme talebi ise tutar bilgileri.",
            "properties": {
                "exists": {"type": "boolean"},
                "amount": {"type": "string", "description": "Toplam tutar, ör. '1.250,00'. Yoksa boş."},
                "currency": {"type": "string", "description": "TRY, USD, EUR... Yoksa boş."},
                "due_date": {"type": "string", "description": "Son ödeme tarihi YYYY-MM-DD; yoksa boş."},
                "issuer": {"type": "string", "description": "Faturayı kesen kurum; yoksa boş."},
            },
            "required": ["exists", "amount", "currency", "due_date", "issuer"],
            "additionalProperties": False,
        },
    },
    "required": ["doc_type", "summary", "tags", "doc_date", "invoice"],
    "additionalProperties": False,
}


def analyze_document(filename: str, text: str) -> dict:
    """Belge metnini sınıflandırır: tür, özet, etiketler, tarih ve fatura alanları."""
    client = _get_client()
    system = (
        "Sen bir belge asistanısın. Kullanıcının belge arşivindeki (dataroom) dosyaları "
        "analiz ediyorsun: belge türünü belirle, kısa Türkçe özet çıkar, arama için "
        "etiketler öner. Fatura/dekont ise tutar, para birimi, son ödeme tarihi ve "
        "kesen kurumu çıkar. Emin olamadığın alanları boş bırak; asla uydurma."
    )
    response = client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=1024,
        system=system,
        output_config={"format": {"type": "json_schema", "schema": DOC_SCHEMA}},
        messages=[
            {
                "role": "user",
                "content": f"Dosya adı: {filename}\n\n--- BELGE METNİ ---\n{text[:20000]}",
            }
        ],
    )
    out = next(b.text for b in response.content if b.type == "text")
    return json.loads(out)


THREAD_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {
            "type": "string",
            "description": "Yazışmanın Türkçe özeti: konu ne, taraflar ne dedi, son durum ne. 2-5 cümle.",
        },
        "action_needed": {
            "type": "string",
            "description": (
                "Kullanıcının yapması gereken somut bir şey varsa tek cümleyle "
                "(ör. 'Fiyat teklifine yanıt bekleniyor'). Yoksa boş string."
            ),
        },
    },
    "required": ["summary", "action_needed"],
    "additionalProperties": False,
}


def summarize_thread(messages: list[dict], user_name: str = "") -> dict:
    """Bir konuşma dizisinin tamamını özetler ve bekleyen aksiyonu çıkarır."""
    client = _get_client()
    system = (
        "Sen bir e-posta asistanısın. Kullanıcıya bir mail yazışmasının (dizinin) "
        "tamamını özetliyorsun: konunun ne olduğunu, kimin ne söylediğini ve son "
        "durumu net biçimde aktar. Özeti her zaman Türkçe yaz."
    )
    if user_name:
        system += f" Kullanıcının adı: {user_name}."
    parts = []
    for i, m in enumerate(messages, 1):
        body = (m.get("body_text") or "")[:6000]
        parts.append(
            f"--- MAİL {i}/{len(messages)} ---\n"
            f"Gönderen: {m.get('sender_name') or ''} <{m.get('sender_email') or ''}>\n"
            f"Tarih: {m.get('date') or ''}\n"
            f"Konu: {m.get('subject') or ''}\n\n{body}"
        )
    response = client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=1024,
        system=system,
        output_config={"format": {"type": "json_schema", "schema": THREAD_SCHEMA}},
        messages=[
            {
                "role": "user",
                "content": "Aşağıdaki mail yazışmasını özetle:\n\n" + "\n\n".join(parts),
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
