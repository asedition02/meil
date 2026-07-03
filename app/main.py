"""Meil — mail tasnif ve yanıt asistanı (FastAPI)."""
import logging

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import ai, config, database, dataroom, email_client

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("meil")

app = FastAPI(title="Meil — E-posta Asistanı")
database.init_db()


def _bootstrap_env_account():
    """.env'de hesap tanımlıysa ve DB boşsa otomatik ekle."""
    if not (config.EMAIL_ADDRESS and config.EMAIL_PASSWORD):
        return
    if database.get_account_by_email(config.EMAIL_ADDRESS):
        return
    database.create_account(
        {
            "display_name": config.EMAIL_ADDRESS,
            "email": config.EMAIL_ADDRESS,
            "password": config.EMAIL_PASSWORD,
            "imap_host": config.IMAP_HOST,
            "imap_port": config.IMAP_PORT,
            "smtp_host": config.SMTP_HOST,
            "smtp_port": config.SMTP_PORT,
            "smtp_security": config.SMTP_SECURITY,
        }
    )
    log.info("Ortam değişkenlerinden hesap eklendi: %s", config.EMAIL_ADDRESS)


_bootstrap_env_account()


class ReplyRequest(BaseModel):
    reply_text: str


class RegenerateRequest(BaseModel):
    instruction: str = ""


class AccountRequest(BaseModel):
    display_name: str = ""
    email: str
    password: str
    provider: str = "custom"  # gmail | outlook | yahoo | yandex | custom
    imap_host: str = ""
    imap_port: int = 993
    smtp_host: str = ""
    smtp_port: int = 465
    smtp_security: str = "ssl"  # ssl | starttls


def _account_dict(req: AccountRequest) -> dict:
    preset = email_client.PRESETS.get(req.provider, {})
    return {
        "display_name": req.display_name.strip() or req.email,
        "email": req.email.strip(),
        "password": req.password,
        "imap_host": preset.get("imap_host") or req.imap_host.strip(),
        "imap_port": preset.get("imap_port") or req.imap_port,
        "smtp_host": preset.get("smtp_host") or req.smtp_host.strip(),
        "smtp_port": preset.get("smtp_port") or req.smtp_port,
        "smtp_security": preset.get("smtp_security") or req.smtp_security,
    }


# ---- Hesaplar ----

@app.get("/api/accounts")
def get_accounts():
    return {"accounts": database.list_accounts(), "presets": list(email_client.PRESETS)}


@app.post("/api/accounts")
def add_account(req: AccountRequest):
    """Hesabı ekler; önce IMAP+SMTP girişini test eder."""
    account = _account_dict(req)
    if database.get_account_by_email(account["email"]):
        raise HTTPException(status_code=409, detail="Bu adres zaten ekli")
    try:
        email_client.test_login(account)
    except (email_client.EmailConfigError, email_client.EmailAuthError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Sunucuya bağlanılamadı: {e}")
    account_id = database.create_account(account)
    return {"ok": True, "id": account_id}


@app.delete("/api/accounts/{account_id}")
def remove_account(account_id: int):
    if not database.get_account(account_id):
        raise HTTPException(status_code=404, detail="Hesap bulunamadı")
    database.delete_account(account_id)
    return {"ok": True}


# ---- Eşitleme ----

def _sync_account(account: dict) -> dict:
    messages = email_client.fetch_recent(account, config.SYNC_LIMIT)
    new_count, errors = 0, []
    for msg in messages:
        if database.email_exists(msg["message_id"], account["id"]):
            continue
        raw_attachments = msg.pop("raw_attachments", [])
        saved = dataroom.save_attachments(msg["sender_email"], msg["date"], raw_attachments)
        msg["attachments"] = saved
        try:
            triage = ai.triage_email(
                sender=f"{msg['sender_name']} <{msg['sender_email']}>",
                subject=msg["subject"],
                date=msg["date"],
                body=msg["body_text"],
                attachments=[a["filename"] for a in saved],
                user_name=config.USER_NAME,
            )
            msg.update(triage)
        except Exception as e:
            log.exception("Tasnif hatası: %s", msg["subject"])
            errors.append(f"{msg['subject']}: {e}")
            msg.update(
                {
                    "category": "Diğer",
                    "priority": "orta",
                    "summary": "(Otomatik tasnif yapılamadı)",
                    "needs_reply": False,
                    "suggested_reply": "",
                }
            )
        database.insert_email(msg)
        new_count += 1
    return {"account": account["email"], "new_emails": new_count,
            "checked": len(messages), "errors": errors}


@app.post("/api/sync")
def sync_emails(account_id: int | None = None):
    """Tüm hesaplardan (veya tek hesaptan) yeni mailleri çeker ve tasnif eder."""
    accounts = (
        [database.get_account(account_id)] if account_id else database.list_accounts(include_password=True)
    )
    accounts = [a for a in accounts if a]
    if not accounts:
        raise HTTPException(
            status_code=400,
            detail="Kayıtlı hesap yok. Hesaplar sekmesinden bir mail hesabı ekleyin.",
        )
    results, total_new = [], 0
    for account in accounts:
        try:
            r = _sync_account(account)
        except (email_client.EmailConfigError, email_client.EmailAuthError) as e:
            r = {"account": account["email"], "new_emails": 0, "checked": 0, "errors": [str(e)]}
        except Exception as e:
            r = {"account": account["email"], "new_emails": 0, "checked": 0,
                 "errors": [f"Bağlantı hatası: {e}"]}
        total_new += r["new_emails"]
        results.append(r)
    return {"new_emails": total_new, "results": results}


# ---- Mailler ----

@app.get("/api/emails")
def list_emails(category: str | None = None, status: str | None = None,
                account_id: int | None = None):
    return {
        "emails": database.list_emails(category=category, status=status, account_id=account_id),
        "counts": database.category_counts(account_id=account_id),
        "categories": ai.CATEGORIES,
    }


@app.get("/api/emails/{email_id}")
def get_email(email_id: int):
    email_data = database.get_email(email_id)
    if not email_data:
        raise HTTPException(status_code=404, detail="Mail bulunamadı")
    return email_data


@app.post("/api/emails/{email_id}/send")
def send_reply(email_id: int, req: ReplyRequest):
    """Kullanıcının onayladığı yanıtı, maili alan hesaptan gönderir."""
    email_data = database.get_email(email_id)
    if not email_data:
        raise HTTPException(status_code=404, detail="Mail bulunamadı")
    if not req.reply_text.strip():
        raise HTTPException(status_code=400, detail="Yanıt metni boş olamaz")
    account = database.get_account(email_data["account_id"]) if email_data["account_id"] else None
    if not account:
        accounts = database.list_accounts(include_password=True)
        if len(accounts) == 1:
            account = accounts[0]
        else:
            raise HTTPException(
                status_code=400,
                detail="Bu mailin hangi hesaba ait olduğu belirlenemedi. Hesabı silip yeniden ekleyin ve maili tekrar eşitleyin.",
            )
    try:
        email_client.send_reply(
            account=account,
            to_address=email_data["sender_email"],
            subject=email_data["subject"] or "",
            body=req.reply_text,
            in_reply_to=email_data["message_id"],
        )
    except (email_client.EmailConfigError, email_client.EmailAuthError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Gönderim başarısız: {e}")
    database.update_email(email_id, status="replied", suggested_reply=req.reply_text)
    return {"ok": True}


@app.post("/api/emails/{email_id}/regenerate")
def regenerate(email_id: int, req: RegenerateRequest):
    """Yanıt taslağını (isteğe bağlı talimatla) yeniden üretir."""
    email_data = database.get_email(email_id)
    if not email_data:
        raise HTTPException(status_code=404, detail="Mail bulunamadı")
    try:
        reply = ai.regenerate_reply(
            sender=f"{email_data['sender_name']} <{email_data['sender_email']}>",
            subject=email_data["subject"] or "",
            date=email_data["date"] or "",
            body=email_data["body_text"] or "",
            instruction=req.instruction,
            user_name=config.USER_NAME,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Taslak üretilemedi: {e}")
    database.update_email(email_id, suggested_reply=reply, needs_reply=1)
    return {"suggested_reply": reply}


@app.post("/api/emails/{email_id}/archive")
def archive_email(email_id: int):
    if not database.get_email(email_id):
        raise HTTPException(status_code=404, detail="Mail bulunamadı")
    database.update_email(email_id, status="archived")
    return {"ok": True}


# ---- Dataroom ----

@app.get("/api/dataroom")
def dataroom_files():
    return {"files": dataroom.list_files()}


@app.get("/api/dataroom/download")
def dataroom_download(path: str):
    try:
        target = dataroom.resolve_file(path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Dosya bulunamadı")
    return FileResponse(target, filename=target.name)


@app.get("/api/status")
def status():
    accounts = database.list_accounts()
    return {
        "accounts": len(accounts),
        "ai_configured": bool(config.ANTHROPIC_API_KEY),
        "model": config.CLAUDE_MODEL,
    }


app.mount("/", StaticFiles(directory=config.BASE_DIR / "static", html=True), name="static")
