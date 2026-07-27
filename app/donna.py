"""Donna — sistemdeki tüm verilere bakan kişisel asistan.

Mailler, takvim ve dataroom'u tek bir bağlamda birleştirir; iki şey yapar:

- brief(): proaktif brifing — "şu an neye bakmalısın": acil yanıt bekleyen
  mailler, bugünün/yaklaşan etkinlikler, yaklaşan fatura son ödemeleri.
- ask(): aynı bağlam üzerinde soru-cevap; yanıt yalnızca gerçek verilere dayanır.

Yanıtlar `ai` modülündeki sağlayıcı yönlendiricisinden geçer, yani Gemini /
NVIDIA / Claude'dan hangisi etkinse onu kullanır.
"""
import datetime as dt
import json

from . import ai, database

MAX_BODY = 900          # bağlama giren mail gövdesi sınırı
NAME = "Donna"


# ---------------------------------------------------------------------------
# Bağlam toplama
# ---------------------------------------------------------------------------

def _fmt_event(e: dict) -> str:
    start = (e.get("start") or "").replace("T", " ")[:16]
    end = (e.get("end") or "").replace("T", " ")[11:16]
    when = start + (f"–{end}" if end and not e.get("all_day") else "")
    if e.get("all_day"):
        when = start[:10] + " (tüm gün)"
    parts = [f"[etkinlik:{e.get('id')}] {when} · {e.get('title') or 'Başlıksız'}"]
    if e.get("location"):
        parts.append(f"yer: {e['location']}")
    if e.get("calendar_name"):
        parts.append(f"takvim: {e['calendar_name']}")
    return " | ".join(parts)


def _fmt_email(m: dict, with_body: bool = False) -> str:
    flags = []
    if m.get("needs_reply"):
        flags.append("YANIT BEKLİYOR")
    if not m.get("is_read"):
        flags.append("okunmadı")
    if m.get("starred"):
        flags.append("yıldızlı")
    if m.get("status") == "replied":
        flags.append("yanıtlanmış")
    line = (
        f"[mail:{m['id']}] {m.get('date') or ''} | "
        f"{m.get('sender_name') or ''} <{m.get('sender_email') or ''}> | "
        f"Konu: {m.get('subject') or '(konusuz)'} | "
        f"{m.get('category') or '?'}/{m.get('priority') or '?'}"
        + (f" | {', '.join(flags)}" if flags else "")
    )
    if m.get("summary"):
        line += f"\n    Özet: {m['summary']}"
    ev = m.get("event_json")
    if ev:
        try:
            d = json.loads(ev)
            if d.get("exists"):
                line += (f"\n    Mailde geçen etkinlik: {d.get('title','')} "
                         f"{d.get('date','')} {d.get('time','')}".rstrip())
        except (ValueError, TypeError):
            pass
    if with_body and m.get("body_text"):
        line += f"\n    İçerik: {m['body_text'][:MAX_BODY]}"
    return line


def gather_context(question: str = "") -> dict:
    """Tüm kaynaklardan Donna'nın bağlamını toplar."""
    today = dt.date.today()
    now = dt.datetime.now()

    counts = database.view_counts()
    attention = database.attention_emails(15)
    events = database.list_events(today.isoformat(),
                                  (today + dt.timedelta(days=14)).isoformat() + "T23:59")
    invoices = database.upcoming_invoices(10)
    docs = database.recent_documents(6)

    # Soru varsa: ilgili mailleri ve belge içeriklerini de ekle
    related_mails, related_docs = [], []
    if question.strip():
        related_mails = database.search_emails_for_chat(question, 10)
        try:
            related_docs = database.search_file_contents(question, 5)
        except Exception:                       # FTS yoksa sessizce geç
            related_docs = []

    return {
        "today": today.isoformat(),
        "now": now.strftime("%Y-%m-%d %H:%M"),
        "weekday": ["Pazartesi", "Salı", "Çarşamba", "Perşembe",
                    "Cuma", "Cumartesi", "Pazar"][today.weekday()],
        "counts": counts,
        "attention": attention,
        "events": events,
        "invoices": invoices,
        "docs": docs,
        "related_mails": related_mails,
        "related_docs": related_docs,
    }


def _context_text(ctx: dict, with_bodies: bool = False) -> str:
    """Bağlamı model için okunur metne çevirir."""
    out = [f"BUGÜN: {ctx['today']} {ctx['weekday']}, saat {ctx['now'][11:]}"]

    c = ctx.get("counts") or {}
    if c:
        out.append(
            "GELEN KUTUSU DURUMU: "
            + ", ".join(f"{k}={v}" for k, v in c.items() if isinstance(v, int))
        )

    if ctx["attention"]:
        out.append("\n=== İLGİ BEKLEYEN MAİLLER ===")
        out += [_fmt_email(m) for m in ctx["attention"]]
    else:
        out.append("\n=== İLGİ BEKLEYEN MAİL YOK ===")

    if ctx["events"]:
        out.append("\n=== TAKVİM (bugün ve önümüzdeki 14 gün) ===")
        out += [_fmt_event(e) for e in ctx["events"][:20]]
    else:
        out.append("\n=== TAKVİMDE YAKLAŞAN ETKİNLİK YOK ===")

    if ctx["invoices"]:
        out.append("\n=== FATURA / DEKONT BELGELERİ ===")
        out += [f"[belge] {i['path']} | {i.get('doc_type','')} | tarih: {i.get('doc_date','')}"
                f" | tutar: {i.get('doc_amount') or '—'}"
                + (f" | {i['ai_summary']}" if i.get("ai_summary") else "")
                for i in ctx["invoices"]]

    if ctx["docs"]:
        out.append("\n=== DATAROOM'DAKİ SON BELGELER ===")
        out += [f"[belge] {d['path']} | {d.get('doc_type','')}"
                + (f" | {d['ai_summary']}" if d.get("ai_summary") else "")
                for d in ctx["docs"]]

    if ctx["related_mails"]:
        out.append("\n=== SORUYLA İLGİLİ MAİLLER (detaylı) ===")
        out += [_fmt_email(m, with_body=with_bodies) for m in ctx["related_mails"]]

    if ctx["related_docs"]:
        out.append("\n=== SORUYLA İLGİLİ BELGE İÇERİKLERİ ===")
        for d in ctx["related_docs"]:
            snippet = (d.get("snippet") or d.get("content") or "")[:500]
            out.append(f"[belge] {d.get('path','')}: {snippet}")

    return "\n".join(out)


# ---------------------------------------------------------------------------
# Kişilik
# ---------------------------------------------------------------------------

PERSONA = """Sen Donna'sın — kullanıcının kişisel asistanı. Mailleri, takvimi ve \
belge arşivini (dataroom) senin gözünden takip ediyor.

Karakterin:
- Kısa, net ve doğrudan konuş. Gereksiz nezaket kalıbı, "elbette", "tabii ki" \
gibi doldurma ifadeler kullanma.
- Kendinden emin ve pratiksin: sadece durumu bildirmekle kalma, ne yapılması \
gerektiğini de söyle.
- Türkçe konuş, kullanıcıya "siz" değil "sen" diye hitap et.
- Sıcak ama profesyonel: arkadaşça, yaltaklanmadan.

Kesin kurallar:
- YALNIZCA sana verilen verilere dayan. Veride olmayan bir şeyi asla uydurma.
- Tarih, saat, tutar ve isimleri verideki gibi aynen aktar.
- Bir şey veride yoksa "bu konuda bir kayıt yok" de.
- Bugünün tarihini kullanarak "yarın", "bu hafta" gibi ifadeleri doğru çöz.
- Mailden bahsederken ilgili mailin ID'sini kaynak olarak belirt."""


BRIEF_SCHEMA = {
    "type": "object",
    "properties": {
        "greeting": {
            "type": "string",
            "description": "Saate uygun kısa selamlama, en fazla 6 kelime (ör. 'Günaydın, işte durum').",
        },
        "headline": {
            "type": "string",
            "description": "Tek cümlelik genel durum özeti (ör. '2 acil yanıt ve bugün 1 toplantın var').",
        },
        "items": {
            "type": "array",
            "description": "Kullanıcının şimdi ilgilenmesi gereken maddeler, önem sırasına göre. En fazla 6 madde. Hiçbir şey yoksa boş bırak.",
            "items": {
                "type": "object",
                "properties": {
                    "kind": {
                        "type": "string",
                        "enum": ["mail", "etkinlik", "fatura", "hatirlatma"],
                        "description": "Maddenin türü.",
                    },
                    "title": {"type": "string", "description": "Kısa başlık, en fazla 8 kelime."},
                    "detail": {
                        "type": "string",
                        "description": "Tek cümlelik açıklama: neden önemli ve ne yapılmalı.",
                    },
                    "urgency": {
                        "type": "string",
                        "enum": ["acil", "normal", "bilgi"],
                        "description": "Aciliyet düzeyi.",
                    },
                    "email_id": {
                        "type": "integer",
                        "description": "Madde bir mailse o mailin ID'si; değilse 0.",
                    },
                },
                "required": ["kind", "title", "detail", "urgency", "email_id"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["greeting", "headline", "items"],
    "additionalProperties": False,
}


ACTION_TYPES = ["yok", "mail_yanitla", "etkinlik_olustur", "etkinlik_guncelle",
                "etkinlik_sil", "belge_sil", "belge_yukle"]

ACTION_SCHEMA = {
    "type": "object",
    "description": (
        "Kullanıcı bir işlem yapılmasını istiyorsa doldur; yalnızca soru sorduysa "
        "type='yok' bırak. İşlem KULLANICI ONAYINDAN SONRA yapılır, sen sadece hazırlarsın."
    ),
    "properties": {
        "type": {"type": "string", "enum": ACTION_TYPES,
                 "description": "Yapılacak işlem türü; işlem yoksa 'yok'."},
        "summary": {"type": "string",
                    "description": "Onay kartında görünecek tek cümlelik açıklama (ör. 'Ayşe'ye yanıt gönderilecek')."},
        "email_id": {"type": "integer", "description": "mail_yanitla için mailin ID'si; değilse 0."},
        "reply_text": {"type": "string",
                       "description": "mail_yanitla için gönderilmeye hazır yanıt metni (imza dahil). Değilse boş."},
        "event_id": {"type": "integer",
                     "description": "etkinlik_guncelle / etkinlik_sil için etkinliğin ID'si; değilse 0."},
        "title": {"type": "string", "description": "Etkinlik başlığı; ilgisizse boş."},
        "date": {"type": "string", "description": "YYYY-MM-DD; ilgisizse boş."},
        "time": {"type": "string", "description": "HH:MM (24 saat); tüm gün ise boş."},
        "duration_minutes": {"type": "integer", "description": "Etkinlik süresi; bilinmiyorsa 60, ilgisizse 0."},
        "location": {"type": "string", "description": "Etkinlik yeri; yoksa boş."},
        "path": {"type": "string", "description": "belge_sil için dataroom dosya yolu; değilse boş."},
    },
    "required": ["type", "summary", "email_id", "reply_text", "event_id",
                 "title", "date", "time", "duration_minutes", "location", "path"],
    "additionalProperties": False,
}

ASK_SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {
            "type": "string",
            "description": "Sorunun Türkçe, kısa ve net yanıtı. Gerekirse madde madde yaz.",
        },
        "email_ids": {
            "type": "array",
            "items": {"type": "integer"},
            "description": "Yanıtta gerçekten kullanılan maillerin ID'leri; kullanılmadıysa boş dizi.",
        },
        "action": ACTION_SCHEMA,
        "follow_ups": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Kullanıcının sorabileceği 2-3 kısa devam sorusu.",
        },
    },
    "required": ["answer", "email_ids", "action", "follow_ups"],
    "additionalProperties": False,
}


# ---------------------------------------------------------------------------
# Genel API
# ---------------------------------------------------------------------------

def brief(user_name: str = "") -> dict:
    """Proaktif brifing: şu an neye bakılmalı."""
    ctx = gather_context()
    system = PERSONA
    if user_name:
        system += f"\n- Kullanıcının adı: {user_name}."
    system += (
        "\n\nGÖREV: Kullanıcıya kısa bir durum brifingi ver. Aciliyet sırasına göz at: "
        "önce yanıt bekleyen ve yüksek öncelikli mailler, sonra bugünkü/yaklaşan "
        "etkinlikler, sonra yaklaşan fatura ödemeleri. Sakin bir gün ise bunu söyle "
        "ve az madde üret — yapay aciliyet yaratma."
    )
    result = ai._generate_json(
        system,
        [{"role": "user", "content": _context_text(ctx) + "\n\nBana kısa bir brifing ver."}],
        BRIEF_SCHEMA, 2048,
    )
    result["stats"] = {
        "attention": len(ctx["attention"]),
        "needs_reply": sum(1 for m in ctx["attention"] if m.get("needs_reply")),
        "today_events": sum(1 for e in ctx["events"]
                            if (e.get("start") or "").startswith(ctx["today"])),
        "events_14d": len(ctx["events"]),
    }
    return result


def ask(question: str, history: list[dict] | None = None, user_name: str = "") -> dict:
    """Tüm veriler üzerinde soru-cevap."""
    ctx = gather_context(question)
    system = PERSONA
    if user_name:
        system += f"\n- Kullanıcının adı: {user_name}."
    system += (
        "\n\nGÖREV: Kullanıcının sorusunu, sana verilen mail/takvim/belge verilerine "
        "dayanarak yanıtla. Yanıtın kısa olsun; gereksiz tekrar yapma."
        "\n\nİŞLEM YAPMA: Kullanıcı bir şey yapılmasını istiyorsa (maile yanıt yaz/gönder, "
        "etkinlik oluştur/güncelle/sil, belge sil veya yükle) `action` alanını doldur:"
        "\n- mail_yanitla: reply_text'e gönderilmeye hazır tam yanıtı yaz; email_id'yi verilerdeki "
        "[mail:ID] değerinden al."
        "\n- etkinlik_olustur: title/date/time/duration_minutes/location doldur; göreli tarihleri "
        "bugünün tarihine göre çöz."
        "\n- etkinlik_guncelle / etkinlik_sil: event_id'yi verilerdeki [etkinlik:ID] değerinden al. "
        "Güncellemede değişmeyen alanları da mevcut değerleriyle doldur."
        "\n- belge_sil: path'i verilerdeki [belge] yolundan aynen al."
        "\n- belge_yukle: dosyayı kullanıcı seçeceği için sadece type ve summary yeterli."
        "\nSadece soru soruluyorsa type='yok' bırak. İşlemi SEN yapmıyorsun — hazırladığın işlem "
        "kullanıcıya onay kartı olarak gösterilir, onaylarsa uygulanır. Bunu yanıtında belirt "
        "(ör. 'Hazırladım, onaylarsan gönderiyorum'). Emin olamadığın bir ID veya yol varsa "
        "işlem üretme, kullanıcıya sor."
    )

    messages = []
    for h in (history or [])[-6:]:
        role = h.get("role")
        content = (h.get("content") or "").strip()
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})
    messages.append({
        "role": "user",
        "content": f"--- VERİLER ---\n{_context_text(ctx, with_bodies=True)}\n\n--- SORU ---\n{question}",
    })

    result = ai._generate_json(system, messages, ASK_SCHEMA, 2048)

    # Kaynak mailleri arayüzde bağlantı olarak göstermek için başlıklarıyla döndür
    ids = result.get("email_ids") or []
    known = {m["id"]: m for m in (ctx["attention"] + ctx["related_mails"])}
    result["sources"] = [
        {"id": i,
         "subject": known[i].get("subject") or "(konusuz)",
         "sender": known[i].get("sender_name") or known[i].get("sender_email") or ""}
        for i in ids if i in known
    ]

    # Önerilen işlemi zenginleştir (onay kartında bağlam göstermek için)
    action = result.get("action") or {}
    if action.get("type") and action["type"] != "yok":
        if action["type"] == "mail_yanitla":
            m = known.get(action.get("email_id"))
            if m:
                action["mail_subject"] = m.get("subject") or "(konusuz)"
                action["mail_to"] = m.get("sender_name") or m.get("sender_email") or ""
            else:
                action["type"] = "yok"          # bilinmeyen mail → işlem üretme
        elif action["type"] in ("etkinlik_guncelle", "etkinlik_sil"):
            ev = next((e for e in ctx["events"] if e.get("id") == action.get("event_id")), None)
            if ev:
                action["event_title"] = ev.get("title") or ""
                action["event_when"] = (ev.get("start") or "").replace("T", " ")[:16]
            else:
                action["type"] = "yok"
        result["action"] = action
    else:
        result["action"] = {"type": "yok"}
    return result


# ---------------------------------------------------------------------------
# Onaylanan işlemin uygulanması
# ---------------------------------------------------------------------------

def describe_action(action: dict) -> str:
    """Onay kartı için kısa, insan tarafından okunur açıklama."""
    t = action.get("type")
    if t == "mail_yanitla":
        return f"{action.get('mail_to') or 'alıcıya'} yanıt gönderilecek"
    if t == "etkinlik_olustur":
        return f"'{action.get('title')}' etkinliği {action.get('date')} {action.get('time')} olarak eklenecek".strip()
    if t == "etkinlik_guncelle":
        return f"'{action.get('event_title') or action.get('title')}' etkinliği güncellenecek"
    if t == "etkinlik_sil":
        return f"'{action.get('event_title')}' etkinliği silinecek"
    if t == "belge_sil":
        return f"{action.get('path')} silinecek"
    if t == "belge_yukle":
        return "Dataroom'a belge yükleme ekranı açılacak"
    return ""

