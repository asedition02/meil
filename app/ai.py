"""Yapay zekâ ile mail tasnifi, özet ve yanıt önerisi.

Sağlayıcı `AI_PROVIDER` ile seçilir: "gemini" (Google Gemini, varsayılan) veya
"claude" (Anthropic). Tüm çağrılar aşağıdaki iki yardımcıdan geçer, böylece
sağlayıcı değiştiğinde iş mantığına dokunmak gerekmez:

- _generate_json(system, messages, schema, max_tokens) → şemaya uygun dict
- _generate_text(system, messages, max_tokens) → düz metin
"""
import json

import requests

from . import config

try:                       # yalnızca Claude kullanılacaksa gerekir
    import anthropic
except ImportError:        # pragma: no cover
    anthropic = None

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

# ---------------------------------------------------------------------------
# Sağlayıcı katmanı
# ---------------------------------------------------------------------------

_client = None
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
_TIMEOUT = 120
# Düşünen modellerde düşünme tokenleri de çıktı bütçesinden düşülür — taban pay
_MIN_OUTPUT_TOKENS = 4096


def _get_client():
    """Anthropic istemcisi (yalnızca claude sağlayıcısında kullanılır)."""
    global _client
    if _client is None:
        if anthropic is None:
            raise RuntimeError("anthropic paketi kurulu değil.")
        if not config.ANTHROPIC_API_KEY:
            raise RuntimeError("ANTHROPIC_API_KEY ayarlanmalı.")
        _client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    return _client


def _gemini_schema(node):
    """JSON Schema → Gemini responseSchema.

    Gemini `additionalProperties` desteklemez; ayrıca alan sırasını korumak için
    `propertyOrdering` ister (yoksa alanlar rastgele sırada üretilebilir).
    """
    if isinstance(node, dict):
        out = {k: _gemini_schema(v) for k, v in node.items() if k != "additionalProperties"}
        if out.get("type") == "object" and isinstance(out.get("properties"), dict):
            out["propertyOrdering"] = list(out["properties"].keys())
        return out
    if isinstance(node, list):
        return [_gemini_schema(v) for v in node]
    return node


def _gemini_call(system: str, messages: list[dict], schema: dict | None,
                 max_tokens: int) -> str:
    if not config.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY ayarlanmalı.")
    contents = [
        # Gemini'de asistan rolünün adı "model"
        {"role": "model" if m["role"] == "assistant" else "user",
         "parts": [{"text": m["content"]}]}
        for m in messages
    ]
    # Gemini 2.5+ modelleri "düşünen" modeller: düşünme tokenleri de
    # maxOutputTokens bütçesinden harcanır (tipik olarak ~1000-1500). Bütçe dar
    # kalırsa yanıt JSON'un ortasında kesilir; bu yüzden taban yükseltiliyor.
    gen: dict = {"maxOutputTokens": max(max_tokens, _MIN_OUTPUT_TOKENS),
                 "temperature": 0.3}
    if schema is not None:
        gen["responseMimeType"] = "application/json"
        gen["responseSchema"] = _gemini_schema(schema)
    payload = {"contents": contents, "generationConfig": gen}
    if system:
        payload["systemInstruction"] = {"parts": [{"text": system}]}

    resp = requests.post(
        GEMINI_URL.format(model=config.GEMINI_MODEL),
        params={"key": config.GEMINI_API_KEY},
        json=payload, timeout=_TIMEOUT,
    )
    if resp.status_code != 200:
        detail = ""
        try:
            detail = resp.json().get("error", {}).get("message", "")
        except ValueError:
            detail = resp.text[:200]
        raise RuntimeError(f"Gemini API hatası ({resp.status_code}): {detail}")

    data = resp.json()
    candidates = data.get("candidates") or []
    if not candidates:
        blocked = (data.get("promptFeedback") or {}).get("blockReason")
        raise RuntimeError(f"Gemini yanıt üretmedi{f' (engellendi: {blocked})' if blocked else ''}.")
    cand = candidates[0]
    text = "".join(p.get("text", "") for p in (cand.get("content") or {}).get("parts", []))
    reason = cand.get("finishReason", "")
    # MAX_TOKENS'ta kısmi metin de dönebilir; JSON yarıda kesilmiş olur
    if reason == "MAX_TOKENS":
        raise RuntimeError(
            "Gemini yanıtı token sınırına takıldı — GEMINI_MODEL için daha yüksek "
            "bütçe gerekiyor ya da içerik çok uzun."
        )
    if not text.strip():
        raise RuntimeError(f"Gemini boş yanıt döndü (finishReason={reason}).")
    return text


def _claude_call(system: str, messages: list[dict], schema: dict | None,
                 max_tokens: int) -> str:
    kwargs = {
        "model": config.CLAUDE_MODEL,
        "max_tokens": max_tokens,
        "system": system,
        "messages": messages,
    }
    if schema is not None:
        kwargs["output_config"] = {"format": {"type": "json_schema", "schema": schema}}
    response = _get_client().messages.create(**kwargs)
    return next(b.text for b in response.content if b.type == "text")


def _generate_text(system: str, messages: list[dict], max_tokens: int = 2048) -> str:
    """Seçili sağlayıcıdan düz metin yanıt alır."""
    if config.AI_PROVIDER == "gemini":
        return _gemini_call(system, messages, None, max_tokens)
    return _claude_call(system, messages, None, max_tokens)


def _generate_json(system: str, messages: list[dict], schema: dict,
                   max_tokens: int = 2048) -> dict:
    """Seçili sağlayıcıdan şemaya uygun JSON alır ve dict olarak döner."""
    if config.AI_PROVIDER == "gemini":
        text = _gemini_call(system, messages, schema, max_tokens)
    else:
        text = _claude_call(system, messages, schema, max_tokens)
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Yapay zekâ geçersiz JSON döndürdü: {e}") from e


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
    system = SYSTEM_PROMPT
    if user_name:
        system += f"\n- Kullanıcının adı: {user_name}. Yanıtları bu isimle imzala."
    return _generate_json(
        system,
        [{"role": "user",
          "content": "Aşağıdaki maili tasnif et:\n\n"
                     + _email_prompt(sender, subject, date, body, attachments)}],
        TRIAGE_SCHEMA, 2048,
    )


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
    result = _generate_json(system, [{"role": "user", "content": prompt}],
                            COMPOSE_SCHEMA, 2048)
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
    system = (
        "Sen bir belge asistanısın. Kullanıcının belge arşivindeki (dataroom) dosyaları "
        "analiz ediyorsun: belge türünü belirle, kısa Türkçe özet çıkar, arama için "
        "etiketler öner. Fatura/dekont ise tutar, para birimi, son ödeme tarihi ve "
        "kesen kurumu çıkar. Emin olamadığın alanları boş bırak; asla uydurma."
    )
    return _generate_json(
        system,
        [{"role": "user",
          "content": f"Dosya adı: {filename}\n\n--- BELGE METNİ ---\n{text[:20000]}"}],
        DOC_SCHEMA, 1024,
    )


CHAT_SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {
            "type": "string",
            "description": "Sorunun Türkçe yanıtı. Yalnızca verilen maillere dayan; "
                           "bilgi yoksa açıkça 'maillerde bulamadım' de.",
        },
        "source_ids": {
            "type": "array",
            "items": {"type": "integer"},
            "description": "Yanıtı dayandırdığın maillerin ID'leri (bağlamda [ID n] olarak verildi). "
                           "Yanıt maillere dayanmıyorsa boş bırak.",
        },
    },
    "required": ["answer", "source_ids"],
    "additionalProperties": False,
}


def answer_inbox_question(question: str, emails: list[dict],
                          history: list[dict] | None = None,
                          user_name: str = "", today: str = "") -> dict:
    """Gelen kutusu hakkındaki soruyu, bulunan maillere dayanarak yanıtlar."""
    system = (
        "Sen kullanıcının e-posta asistanısın. Kullanıcı gelen kutusu hakkında soru "
        "soruyor; sana sorusuyla ilgili bulunabilen mailler veriliyor.\n"
        "- YALNIZCA verilen maillere dayan; uydurma, tahmin etme.\n"
        "- Yanıtı her zaman Türkçe, kısa ve net yaz; tarih/tutar/isim gibi somut "
        "bilgileri aynen aktar.\n"
        "- Sorunun yanıtı maillerde yoksa bunu açıkça söyle.\n"
        "- source_ids alanına yalnızca gerçekten kullandığın maillerin ID'lerini koy."
    )
    if user_name:
        system += f"\n- Kullanıcının adı: {user_name}."
    if today:
        system += f"\n- Bugünün tarihi: {today}."
    parts = []
    for m in emails:
        body = (m.get("body_text") or "")[:1500]
        parts.append(
            f"[ID {m['id']}] Kimden: {m.get('sender_name') or ''} <{m.get('sender_email') or ''}> | "
            f"Tarih: {m.get('date') or ''} | Konu: {m.get('subject') or ''} | "
            f"Durum: {m.get('status') or ''}\n"
            f"Özet: {m.get('summary') or ''}\nİçerik: {body}"
        )
    context = "\n\n".join(parts) if parts else "(İlgili mail bulunamadı.)"
    messages = []
    for h in (history or [])[-6:]:
        role = h.get("role")
        content = (h.get("content") or "").strip()
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})
    messages.append({
        "role": "user",
        "content": f"--- GELEN KUTUSUNDAN İLGİLİ MAİLLER ---\n{context}\n\n--- SORU ---\n{question}",
    })
    return _generate_json(system, messages, CHAT_SCHEMA, 1024)


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
    return _generate_json(
        system,
        [{"role": "user",
          "content": "Aşağıdaki mail yazışmasını özetle:\n\n" + "\n\n".join(parts)}],
        THREAD_SCHEMA, 1024,
    )


def regenerate_reply(sender: str, subject: str, date: str, body: str,
                     instruction: str = "", user_name: str = "") -> str:
    """Kullanıcının ek talimatıyla yeni bir yanıt taslağı üretir."""
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
    return _generate_text(system, [{"role": "user", "content": prompt}], 2048).strip()
