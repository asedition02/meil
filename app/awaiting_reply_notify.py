"""'Cevap bekliyorum' takibi için arka plan işi: bildirim maili.

Header tabanlı otomatik çözümleme (`database.resolve_awaiting_replies_by_headers`)
zaten `emails` tablosuna bakar — yeni mail çekmek bu modülün işi değil, hesap
senkronu ayrı bir zamanlayıcı işi olarak `app/main.py`de kayıtlıdır. Bu modül
her tick'te önce çözümlemeyi dener, sonra süresi geçmiş ama henüz bildirilmemiş
kayıtlar için tek seferlik e-posta gönderir.

Ayrı bir modül olmasının nedeni: reminder_notify.py'deki gerekçeyle aynı —
app/main.py import edilirken database.init_db() çalıştırır (gerçek DB'ye
dokunur); testler bu yan etkiyi tetiklemeden yalnızca bu mantığı import
edebilsin diye kendi dosyasında yaşıyor.
"""
import datetime as dt
import logging

from . import database, email_client

log = logging.getLogger("meil.awaiting_replies")


def _now_iso() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def resolve_and_notify():
    database.resolve_awaiting_replies_by_headers()

    due = database.due_awaiting_replies_unnotified(_now_iso())
    if not due:
        return
    accounts = database.list_accounts()
    if not accounts:
        return
    account = database.get_account(accounts[0]["id"])
    if not account:
        return
    for r in due:
        who = r["to_name"] or r["to_email"]
        try:
            email_client.send_message(
                account, account["email"], f"Hâlâ cevap bekliyor: {who}",
                f'{who} kişisine gönderdiğiniz "{r["subject"]}" konulu maile '
                f"henüz yanıt gelmedi.\n\n— Meil",
            )
        except Exception:
            log.exception("Cevap-bekleme bildirimi gönderilemedi (id=%s)", r["id"])
            continue
        database.mark_awaiting_reply_notified(r["id"])
