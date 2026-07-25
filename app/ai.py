"""Yapay zekâ ile mail tasnifi, özet ve yanıt önerisi.

Sağlayıcı `AI_PROVIDER` ile seçilir: "gemini" (Google Gemini, varsayılan) veya
"claude" (Anthropic). Tüm çağrılar aşağıdaki iki yardımcıdan geçer, böylece
sağlayıcı değiştiğinde iş mantığına dokunmak gerekmez:

- _generate_json(system, messages, schema, max_tokens) → şemaya uygun dict
- _generate_text(system, messages, max_tokens) → düz metin
"""
import json
import logging
import time
from collections import deque

import requests

from . import config, database

log = logging.getLogger("meil.ai")

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


def _nvidia_call(system: str, messages: list[dict], schema: dict | None,
                 max_tokens: int) -> str:
    """NVIDIA NIM (OpenAI uyumlu sohbet API'si).

    Şema desteği modelden modele değiştiği için JSON, hem `response_format` ile
    hem de şemayı sistem istemine gömerek istenir; yanıt savunmacı ayrıştırılır.
    """
    if not config.NVIDIA_API_KEY:
        raise RuntimeError("NVIDIA_API_KEY ayarlanmalı.")
    sys_text = system
    if schema is not None:
        sys_text += (
            "\n\nYANIT BİÇİMİ: Yalnızca aşağıdaki JSON şemasına uyan tek bir JSON "
            "nesnesi döndür. Açıklama, markdown veya kod bloğu ekleme.\n"
            + json.dumps(schema, ensure_ascii=False)
        )
    payload = {
        "model": config.NVIDIA_MODEL,
        "messages": [{"role": "system", "content": sys_text}] + messages,
        "max_tokens": max_tokens,
        "temperature": 0.3,
    }
    if schema is not None:
        payload["response_format"] = {"type": "json_object"}

    url = config.NVIDIA_BASE_URL.rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {config.NVIDIA_API_KEY}",
               "Content-Type": "application/json"}
    resp = requests.post(url, json=payload, headers=headers, timeout=_TIMEOUT)
    if resp.status_code == 400 and schema is not None:
        # Model response_format'ı desteklemiyor olabilir — istem yönergesiyle tekrar dene
        payload.pop("response_format", None)
        resp = requests.post(url, json=payload, headers=headers, timeout=_TIMEOUT)
    if resp.status_code != 200:
        detail = ""
        try:
            body = resp.json()
            detail = (body.get("detail") or body.get("error")
                      or body.get("message") or json.dumps(body))
            if isinstance(detail, dict):
                detail = detail.get("message") or json.dumps(detail)
        except ValueError:
            detail = resp.text[:200]
        raise RuntimeError(f"NVIDIA API hatası ({resp.status_code}): {str(detail)[:300]}")

    data = resp.json()
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError("NVIDIA boş yanıt döndü.")
    msg = choices[0].get("message") or {}
    text = (msg.get("content") or "").strip()
    if not text:
        # Bazı akıl yürüten modeller içeriği reasoning_content alanına koyar
        text = (msg.get("reasoning_content") or "").strip()
    if not text:
        raise RuntimeError(
            f"NVIDIA boş içerik döndü (finish_reason={choices[0].get('finish_reason')})."
        )
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


# ---------------------------------------------------------------------------
# Yönlendirici: sağlayıcı seçimi, sağlık takibi ve yedekleme
# ---------------------------------------------------------------------------

PROVIDERS = ("gemini", "nvidia", "claude")
PROVIDER_LABELS = {"gemini": "Google Gemini", "nvidia": "NVIDIA NIM", "claude": "Anthropic Claude"}
_CALLERS = {"gemini": _gemini_call, "nvidia": _nvidia_call, "claude": _claude_call}

_COOLDOWN_SECONDS = 180      # hata veren sağlayıcı bu süre boyunca geri planda
_SETTING_KEY = "ai_provider"

# Sağlayıcı sağlık istatistikleri (bellekte; süreç yeniden başlayınca sıfırlanır)
_stats: dict[str, dict] = {
    p: {"ok": 0, "fail": 0, "latencies": deque(maxlen=20),
        "last_error": "", "cooldown_until": 0.0}
    for p in PROVIDERS
}


def provider_configured(name: str) -> bool:
    return bool(config.API_KEYS.get(name))


def provider_model(name: str) -> str:
    return config.MODELS.get(name, "")


def available_providers() -> list[str]:
    return [p for p in PROVIDERS if provider_configured(p)]


def selected_provider() -> str:
    """Kullanıcının seçimi: veritabanı > .env > 'auto'."""
    stored = database.get_setting(_SETTING_KEY)
    choice = (stored or config.AI_PROVIDER or "auto").strip().lower()
    return choice if choice in PROVIDERS or choice == "auto" else "auto"


def set_selected_provider(name: str) -> None:
    name = (name or "").strip().lower()
    if name not in PROVIDERS and name != "auto":
        raise ValueError("Geçersiz sağlayıcı")
    database.set_setting(_SETTING_KEY, name)


def _avg_latency(name: str) -> float:
    lat = _stats[name]["latencies"]
    return sum(lat) / len(lat) if lat else 0.0


def _score(name: str) -> tuple:
    """Küçük skor daha iyi: önce soğuma durumu, sonra ölçülen gecikme."""
    st = _stats[name]
    in_cooldown = 1 if st["cooldown_until"] > time.time() else 0
    # Hiç denenmemiş sağlayıcı ortada bir gecikmeyle başlar ki şansı olsun
    latency = _avg_latency(name) or 3.0
    return (in_cooldown, latency)


def _order_for_auto() -> list[str]:
    return sorted(available_providers(), key=_score)


def active_provider() -> str:
    """Şu anda kullanılacak sağlayıcı (auto ise en iyi durumdaki)."""
    choice = selected_provider()
    if choice != "auto":
        return choice
    order = _order_for_auto()
    return order[0] if order else ""


def provider_status() -> list[dict]:
    """Arayüz için sağlayıcı listesi ve sağlık bilgisi."""
    now = time.time()
    active = active_provider()
    out = []
    for p in PROVIDERS:
        st = _stats[p]
        out.append({
            "name": p,
            "label": PROVIDER_LABELS[p],
            "model": provider_model(p),
            "configured": provider_configured(p),
            "active": p == active,
            "ok": st["ok"],
            "fail": st["fail"],
            "avg_ms": round(_avg_latency(p) * 1000) if st["latencies"] else None,
            "cooldown": max(0, round(st["cooldown_until"] - now)),
            "last_error": st["last_error"][:200],
        })
    return out


def _record(name: str, elapsed: float, error: str = "") -> None:
    st = _stats[name]
    if error:
        st["fail"] += 1
        st["last_error"] = error
        st["cooldown_until"] = time.time() + _COOLDOWN_SECONDS
    else:
        st["ok"] += 1
        st["last_error"] = ""
        st["cooldown_until"] = 0.0
        st["latencies"].append(elapsed)


def _call_chain() -> list[str]:
    """Denenecek sağlayıcılar: seçilen önce, sonra yedekler."""
    avail = available_providers()
    if not avail:
        raise RuntimeError(
            "Yapay zekâ sağlayıcısı ayarlanmadı — .env dosyasına GEMINI_API_KEY, "
            "NVIDIA_API_KEY veya ANTHROPIC_API_KEY ekleyin."
        )
    choice = selected_provider()
    if choice == "auto":
        return _order_for_auto()
    if choice in avail:
        # Kullanıcı belirli bir sağlayıcı seçtiyse önce onu dene, sonra diğerleri
        return [choice] + [p for p in _order_for_auto() if p != choice]
    return _order_for_auto()


def _dispatch(system: str, messages: list[dict], schema: dict | None,
              max_tokens: int) -> str:
    """Sağlayıcı zincirini sırayla dener; biri başarılı olana kadar devam eder."""
    errors = []
    for name in _call_chain():
        started = time.time()
        try:
            text = _CALLERS[name](system, messages, schema, max_tokens)
            _record(name, time.time() - started)
            return text
        except Exception as e:                       # noqa: BLE001 — yedeğe geç
            _record(name, time.time() - started, str(e))
            errors.append(f"{PROVIDER_LABELS[name]}: {e}")
            log.warning("AI sağlayıcı başarısız (%s): %s", name, e)
    raise RuntimeError("Tüm yapay zekâ sağlayıcıları başarısız oldu — " + " | ".join(errors))


def _extract_json(text: str) -> dict:
    """Yanıttan JSON çıkarır: kod bloğu çitleri ve çevre metni tolere eder."""
    raw = text.strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1] if raw.count("```") >= 2 else raw.strip("`")
        raw = raw.split("\n", 1)[1] if raw.lower().startswith(("json\n", "json\r")) else raw
        raw = raw.strip().rstrip("`").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start, end = raw.find("{"), raw.rfind("}")
        if start != -1 and end > start:
            return json.loads(raw[start:end + 1])
        raise


def _generate_text(system: str, messages: list[dict], max_tokens: int = 2048) -> str:
    """Etkin sağlayıcıdan düz metin yanıt alır (gerekirse yedeğe geçer)."""
    return _dispatch(system, messages, None, max_tokens)


def _generate_json(system: str, messages: list[dict], schema: dict,
                   max_tokens: int = 2048) -> dict:
    """Etkin sağlayıcıdan şemaya uygun JSON alır ve dict olarak döner."""
    text = _dispatch(system, messages, schema, max_tokens)
    try:
        return _extract_json(text)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Yapay zekâ geçersiz JSON döndürdü: {e}") from e


def test_provider(name: str) -> dict:
    """Tek bir sağlayıcıyı küçük bir istekle sınar (arayüzdeki 'Test Et')."""
    if name not in PROVIDERS:
        raise ValueError("Geçersiz sağlayıcı")
    if not provider_configured(name):
        return {"ok": False, "error": "API anahtarı ayarlanmadı"}
    started = time.time()
    try:
        text = _CALLERS[name](
            "Sen bir test asistanısın. Tek kelimeyle yanıt ver.",
            [{"role": "user", "content": "Çalışıyor musun? Yalnızca 'evet' yaz."}],
            None, 64,
        )
        elapsed = time.time() - started
        _record(name, elapsed)
        return {"ok": True, "ms": round(elapsed * 1000),
                "model": provider_model(name), "reply": text.strip()[:80]}
    except Exception as e:                            # noqa: BLE001
        _record(name, time.time() - started, str(e))
        return {"ok": False, "error": str(e)[:300], "model": provider_model(name)}


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
