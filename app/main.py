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


class ReplyRequest(BaseModel):
    reply_text: str


class RegenerateRequest(BaseModel):
    instruction: str = ""


@app.post("/api/sync")
def sync_emails():
    """Gelen kutusundan yeni mailleri çeker, tasnif eder, ekleri dataroom'a kaydeder."""
    try:
        messages = email_client.fetch_recent(config.SYNC_LIMIT)
    except email_client.EmailConfigError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Mail sunucusuna bağlanılamadı: {e}")

    new_count, errors = 0, []
    for msg in messages:
        if database.email_exists(msg["message_id"]):
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

    return {"new_emails": new_count, "checked": len(messages), "errors": errors}


@app.get("/api/emails")
def list_emails(category: str | None = None, status: str | None = None):
    return {
        "emails": database.list_emails(category=category, status=status),
        "counts": database.category_counts(),
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
    """Kullanıcının onayladığı yanıtı gönderir."""
    email_data = database.get_email(email_id)
    if not email_data:
        raise HTTPException(status_code=404, detail="Mail bulunamadı")
    if not req.reply_text.strip():
        raise HTTPException(status_code=400, detail="Yanıt metni boş olamaz")
    try:
        email_client.send_reply(
            to_address=email_data["sender_email"],
            subject=email_data["subject"] or "",
            body=req.reply_text,
            in_reply_to=email_data["message_id"],
        )
    except email_client.EmailConfigError as e:
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
    return {
        "email_configured": bool(config.EMAIL_ADDRESS and config.EMAIL_PASSWORD),
        "ai_configured": bool(config.ANTHROPIC_API_KEY),
        "email_address": config.EMAIL_ADDRESS,
        "model": config.CLAUDE_MODEL,
    }


app.mount("/", StaticFiles(directory=config.BASE_DIR / "static", html=True), name="static")
