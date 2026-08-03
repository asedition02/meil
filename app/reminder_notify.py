"""Zamanı gelen hatırlatmalar için tek seferlik e-posta bildirimi.

Zamanlayıcı (app/scheduler.py) tarafından her tick'te çağrılır. Uygulama-içi
görünürlük (Bugün ekranı) bu modülden bağımsızdır — doğrudan `remind_at <= now`
hesaplamasına bakar. Bu modül yalnızca kendine "hatırlatma zamanı geldi"
maili göndermekten sorumludur; hesap yoksa ya da gönderim başarısız olursa
sessizce loglar ve bir sonraki tick'te tekrar dener (notified_at set edilmez).

Ayrı bir modül olmasının nedeni: app/main.py import edilirken FastAPI app'i
kurar ve database.init_db() çalıştırır (gerçek DB'ye dokunur) — testlerin bu
yan etkiyi tetiklemeden yalnızca bildirim mantığını import edebilmesi için
bu iş kendi dosyasında yaşıyor.
"""
import datetime as dt
import logging

from . import database, email_client, push_notify

log = logging.getLogger("meil.reminders")


def _now_iso() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def notify_due_reminders():
    """Zamanı gelmiş, henüz bildirilmemiş hatırlatmalar için e-posta + push gönderir."""
    due = database.due_reminders_unnotified(_now_iso())
    if not due:
        return
    accounts = database.list_accounts()
    if not accounts:
        return
    account = database.get_account(accounts[0]["id"])
    if not account:
        return
    for r in due:
        title = f"Hatırlatma: {r['text']}"
        try:
            email_client.send_message(
                account, account["email"], title,
                f"Hatırlatma zamanı geldi:\n\n{r['text']}\n\n— Meil",
            )
        except Exception:
            log.exception("Hatırlatma e-postası gönderilemedi (id=%s)", r["id"])
            continue
        try:
            push_notify.send_push(title, "Hatırlatma zamanı geldi.")
        except Exception:
            log.exception("Hatırlatma push bildirimi gönderilemedi (id=%s)", r["id"])
        database.mark_reminder_notified(r["id"])
