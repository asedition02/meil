"""Doğal dil ile oluşturulan otomasyonlar.

Şu an desteklenen tek kural türü: "X kişisinden N gün/saat içinde yanıt
gelmezse bana bildir". Donna'nın ask() akışı kullanıcının cümlesini
ACTION_SCHEMA'daki otomasyon alanlarına döker (donna.py); bu modül o alanları
- önizleme için zenginleştirir (enrich_action),
- onaylandığında kaydeder (create),
- kullanıcı bir maile yanıt verdiğinde bekleme saatini başlatır (on_reply_sent),
- periyodik olarak (her /api/sync çağrısında) süresi dolanları değerlendirip
  bildirim üretir (check_due).

Onay olmadan hiçbir mail gönderilmez / silinmez — bu modülün tek etkisi bir
uygulama içi bildirim oluşturmaktır.
"""
import datetime as dt
import logging

from . import database, push_notify

log = logging.getLogger("meil.automations")

INTERVAL_UNITS = ("saat", "gun")
UNIT_LABELS = {"saat": "saat", "gun": "gün"}


def interval_text(value: int, unit: str) -> str:
    return f"{value} {UNIT_LABELS.get(unit, 'gün')}"


def _interval_hours(value: int, unit: str) -> int:
    return value * (1 if unit == "saat" else 24)


def _names_match(a: str, b: str) -> bool:
    a, b = (a or "").strip().lower(), (b or "").strip().lower()
    if not a or not b:
        return False
    return a in b or b in a


# ---------------------------------------------------------------------------
# Donna onay kartı için zenginleştirme
# ---------------------------------------------------------------------------

def enrich_action(action: dict) -> dict:
    """Donna'nın ürettiği otomasyon alanlarını doğrular ve önizleme metni ekler.

    Geçersiz/desteklenmeyen bir istekse action['type'] 'yok'a çevrilir —
    diğer aksiyon türlerindeki "bilinmeyen ID → işlem üretme" kuralıyla aynı.
    """
    if action.get("type") != "otomasyon_olustur":
        return action

    sender = (action.get("automation_sender") or "").strip()
    unit = (action.get("automation_interval_unit") or "").strip()
    act_type = (action.get("automation_action") or "bildir").strip()
    try:
        value = int(action.get("automation_interval_value") or 0)
    except (TypeError, ValueError):
        value = 0

    if act_type != "bildir" or not sender or value <= 0 or unit not in INTERVAL_UNITS:
        action["type"] = "yok"
        return action

    match = database.find_sender(sender)
    sender_email = (match or {}).get("sender_email") or ""
    awaiting = database.find_awaiting_thread(sender, sender_email)
    itext = interval_text(value, unit)

    action["automation_interval_text"] = itext
    action["automation_sender_email"] = sender_email

    if awaiting:
        action["automation_note"] = (
            f"{sender} ile açık bir konuşma var — ona son yanıtından bu yana bekleniyor. "
            f"{itext} içinde ondan yeni mail gelmezse hemen bildireceğim."
        )
    elif match:
        action["automation_note"] = (
            f"{sender} ile eşleşen kayıtlı mailler var ama şu an bekleyen bir konuşma yok. "
            "Kural, ona bir sonraki yanıtını gönderdiğin an devreye girecek."
        )
    else:
        action["automation_note"] = (
            f"Kayıtlarda \"{sender}\" ile eşleşen bir mail bulamadım. "
            "Kural yine de kaydedilecek; ona ilk yanıtı gönderdiğinde otomatik olarak izlemeye başlayacağım."
        )

    action["summary"] = f"{sender} kişisinden {itext} içinde yanıt gelmezse sana bildireceğim"
    return action


# ---------------------------------------------------------------------------
# Kaydet / yönet
# ---------------------------------------------------------------------------

def create(sender: str, interval_value: int, interval_unit: str, raw_text: str = "") -> dict:
    sender = (sender or "").strip()
    if not sender:
        raise ValueError("Gönderen adı gerekli")
    try:
        interval_value = int(interval_value)
    except (TypeError, ValueError):
        interval_value = 0
    if interval_value <= 0:
        raise ValueError("Süre 0'dan büyük olmalı")
    if interval_unit not in INTERVAL_UNITS:
        raise ValueError("Süre birimi 'saat' veya 'gun' olmalı")

    match = database.find_sender(sender)
    sender_email = (match or {}).get("sender_email") or ""
    awaiting = database.find_awaiting_thread(sender, sender_email)

    automation_id = database.create_automation({
        "raw_text": raw_text or f"{sender} kişisinden {interval_text(interval_value, interval_unit)} içinde yanıt gelmezse bildir",
        "trigger_type": "yanit_gelmezse",
        "sender_name": sender,
        "sender_email": sender_email,
        "interval_value": interval_value,
        "interval_unit": interval_unit,
        "action_type": "bildir",
        "account_id": awaiting["account_id"] if awaiting else None,
        "thread_id": awaiting["thread_id"] if awaiting else None,
        "waiting_since": awaiting["date"] if awaiting else None,
    })
    return database.get_automation(automation_id)


def list_all() -> list[dict]:
    out = []
    for a in database.list_automations():
        a = dict(a)
        a["interval_text"] = interval_text(a["interval_value"], a["interval_unit"])
        a["waiting"] = bool(a.get("waiting_since"))
        out.append(a)
    return out


def remove(automation_id: int):
    database.delete_automation(automation_id)


def set_status(automation_id: int, active: bool):
    database.update_automation(automation_id, status="active" if active else "paused")


# ---------------------------------------------------------------------------
# Çalışma zamanı: yanıt gönderilince kolla, süresi dolanları bildir
# ---------------------------------------------------------------------------

def on_reply_sent(email_row: dict):
    """Kullanıcı bir maile yanıt gönderdiğinde çağrılır.

    O göndereni izleyen aktif otomasyonların bekleme saatini şimdi başlatır —
    "ondan N gün içinde yanıt gelmezse bildir" kuralı artık gerçekten kolluyor demektir.
    """
    sender_email = (email_row.get("sender_email") or "").strip()
    sender_name = (email_row.get("sender_name") or "").strip()
    if not sender_email and not sender_name:
        return
    now = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    for auto in database.active_automations("yanit_gelmezse"):
        if auto["sender_email"]:
            matched = sender_email and auto["sender_email"].lower() == sender_email.lower()
        else:
            matched = _names_match(auto["sender_name"], sender_name)
        if not matched:
            continue
        database.update_automation(
            auto["id"],
            sender_email=auto["sender_email"] or sender_email,
            account_id=email_row.get("account_id"),
            thread_id=email_row.get("thread_id"),
            waiting_since=now,
        )


def check_due() -> list[dict]:
    """Bekleme süresi dolan otomasyonları değerlendirir, gerekiyorsa bildirim üretir.

    Tetiklenen kuralın bekleme saati sıfırlanır (kural etkin kalır ve bir
    dahaki yanıtta yeniden kollamaya başlar). Döner: oluşturulan bildirimler.
    """
    created = []
    now = dt.datetime.now().astimezone()
    for auto in database.active_automations("yanit_gelmezse"):
        if not auto.get("waiting_since"):
            continue
        try:
            since = dt.datetime.fromisoformat(auto["waiting_since"])
        except ValueError:
            database.update_automation(auto["id"], waiting_since=None)
            continue
        if now - since < dt.timedelta(hours=_interval_hours(auto["interval_value"], auto["interval_unit"])):
            continue
        if auto["thread_id"] and auto["sender_email"] and database.newer_message_exists(
            auto["account_id"], auto["thread_id"], auto["sender_email"], auto["waiting_since"]
        ):
            database.update_automation(auto["id"], waiting_since=None)  # yanıt zaten gelmiş
            continue
        itext = interval_text(auto["interval_value"], auto["interval_unit"])
        who = auto["sender_name"] or auto["sender_email"] or "Gönderen"
        title = f"{who} yanıt vermedi"
        body = f"{who} kişisinden {itext} içinde yanıt gelmedi."
        nid = database.create_notification(auto["id"], title, body)
        try:
            push_notify.send_push(title, body)
        except Exception:
            log.exception("Otomasyon push bildirimi gönderilemedi (id=%s)", auto["id"])
        database.update_automation(
            auto["id"], waiting_since=None,
            last_triggered_at=now.isoformat(timespec="seconds"),
        )
        created.append({"id": nid, "title": title, "body": body})
    return created
